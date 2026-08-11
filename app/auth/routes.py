import re
from pathlib import Path
from urllib.parse import urljoin
from uuid import uuid4

from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.security import check_password_hash, generate_password_hash

from app.auth import auth_bp
from app.auth.tokens import (
    generate_email_verification_token,
    generate_password_reset_token,
    verify_email_verification_token,
    verify_password_reset_token,
)
from app.models import User
from app.models.base import utc_now
from app.services.email import send_email
from extensions import db, limiter


ALLOWED_IMAGE_FORMATS = {'JPEG', 'PNG', 'WEBP'}
PHONE_PATTERN = re.compile(r'^\+?[0-9\s()\-]{7,20}$')

# Var olmayan bir e-posta denendiğinde de parola doğrulama maliyetini ödemek
# için kullanılır. Yanıt süresi farkından hesap varlığı anlaşılmasın diye.
DUMMY_PASSWORD_HASH = generate_password_hash('flowdesk-timing-guard')


def login_attempt_failed(response):
    """Rate limit sayacı yalnızca başarısız girişlerde artar."""
    return response.status_code != 302


def application_url(endpoint, **values):
    """E-posta bağlantılarını istek başlığından değil güvenilir ayardan üretir."""
    path = url_for(endpoint, **values)
    return urljoin(
        current_app.config['APP_BASE_URL'] + '/',
        path.lstrip('/')
    )


def send_verification_email(user):
    token = generate_email_verification_token(user)
    verification_url = application_url(
        'auth.verify_email',
        token=token
    )
    expires_hours = current_app.config['EMAIL_VERIFICATION_MAX_AGE'] // 3600

    send_email(
        subject='FlowDesk e-posta adresinizi doğrulayın',
        recipient=user.email,
        text_body=render_template(
            'emails/verify_email.txt',
            user=user,
            verification_url=verification_url,
            expires_hours=expires_hours
        ),
        html_body=render_template(
            'emails/verify_email.html',
            user=user,
            verification_url=verification_url,
            expires_hours=expires_hours
        )
    )


def save_profile_image(upload):
    """Yüklenen resmi doğrular, kare WebP dosyasına dönüştürür ve kaydeder."""
    try:
        upload.stream.seek(0)
        with Image.open(upload.stream) as source:
            source.verify()

        upload.stream.seek(0)
        with Image.open(upload.stream) as source:
            if source.format not in ALLOWED_IMAGE_FORMATS:
                raise ValueError('Yalnızca JPG, PNG veya WebP fotoğraf yükleyebilirsiniz.')

            image = ImageOps.exif_transpose(source).convert('RGB')
            image = ImageOps.fit(
                image,
                (512, 512),
                method=Image.Resampling.LANCZOS
            )

            upload_folder = Path(current_app.config['PROFILE_IMAGE_UPLOAD_FOLDER'])
            upload_folder.mkdir(parents=True, exist_ok=True)

            filename = f'{uuid4().hex}.webp'
            image.save(
                upload_folder / filename,
                format='WEBP',
                quality=85,
                method=6
            )
            return filename
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise ValueError('Seçtiğiniz dosya geçerli bir fotoğraf değil.')


def delete_profile_image(filename):
    """Kullanıcının eski profil fotoğrafını güvenli biçimde siler."""
    if not filename:
        return

    safe_filename = Path(filename).name
    image_path = Path(
        current_app.config['PROFILE_IMAGE_UPLOAD_FOLDER']
    ) / safe_filename

    if image_path.is_file():
        image_path.unlink()

@auth_bp.route('/register')
def register():
    return render_template('auth/register_choice.html')


@auth_bp.route('/register/personnel', methods=['GET', 'POST'])
@limiter.limit(
    lambda: current_app.config['REGISTER_RATELIMIT'],
    methods=['POST']
)
def register_personnel():
    return register_account(
        account_type='Personnel',
        endpoint='auth.register_personnel'
    )


@auth_bp.route('/register/intern', methods=['GET', 'POST'])
@limiter.limit(
    lambda: current_app.config['REGISTER_RATELIMIT'],
    methods=['POST']
)
def register_intern():
    return register_account(
        account_type='Intern',
        endpoint='auth.register_intern'
    )


def register_account(account_type, endpoint):
    errors = []
    username = ''
    email = ''

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email' , '').strip().lower()
        password = request.form.get('password' , '')
        password_confirm = request.form.get('password_confirm' , '')

        if not username:
            errors.append('Kullanıcı Adı gereklidir.')
        elif len(username) < 3:
            errors.append('Kullanıcı Adı en az 3 karakter olmalıdır.')
        elif len(username) > 50:
            errors.append('Kullanıcı Adı en fazla 50 karakter olmalıdır.')
        
        if not email:
            errors.append('E-posta adresi gereklidir.')
        elif '@' not in email or '.' not in email.split('@')[-1]:
            errors.append('Geçerli bir e-posta adresi girin.')
        elif len(email) > 120:
            errors.append('E-posta adresi en fazla 120 karakter olabilir.')

        if not password:
            errors.append('Parola gereklidir.')
        elif len(password) < 8:
            errors.append('Parola en az 8 karakter olmalıdır.')

        if not password_confirm:
            errors.append('Parola tekrarı gereklidir.')
        elif password != password_confirm:
            errors.append('Parolalar birbiriyle eşleşmiyor.')

        if not errors:
            existing_username = db.session.scalar(
                db.select(User).where(User.username == username)
            )
            existing_email = db.session.scalar(
                db.select(User).where(User.email == email)
            )

            if existing_username:
                errors.append('Bu kullanıcı adı daha önce kullanılmış.')
            if existing_email:
                errors.append('Bu e-posta adresi daha önce kullanılmış.')
        if not errors:
            user = User(
                username = username,
                email = email,
                email_verified=False,
                account_type=account_type
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            try:
                send_verification_email(user)
            except Exception:
                current_app.logger.exception(
                    'E-posta doğrulama bağlantısı gönderilemedi.'
                )
            flash(
                'Hesabınız oluşturuldu. Giriş yapmadan önce e-posta '
                'adresinize gönderilen bağlantıyla hesabınızı doğrulayın.',
                'success'
            )
            return redirect(url_for('auth.login'))
        
        return render_template(
            'auth/register.html',
            errors = errors,
            username = username,
            email = email,
            account_type=account_type,
            registration_endpoint=endpoint
        )
    return render_template(
        'auth/register.html',
        account_type=account_type,
        registration_endpoint=endpoint
    )


@auth_bp.route('/login' , methods = ['GET' , 'POST'])
@limiter.limit(
    lambda: current_app.config['LOGIN_RATELIMIT'],
    methods=['POST'],
    deduct_when=login_attempt_failed,
    error_message=(
        'Çok fazla başarısız giriş denemesi yapıldı. '
        'Lütfen bir süre sonra yeniden deneyin.'
    )
)
def login():
    errors = []
    email = ''

    if request.method == 'POST':
        email = request.form.get('email' , '').strip().lower()
        password = request.form.get('password' , '')
        remember = request.form.get('remember') == 'on'

        if not email:
            errors.append('E-posta adresi gereklidir.')

        if not password:
            errors.append('Parola gereklidir.')

        if not errors:
            user = db.session.scalar(
                db.select(User).where(User.email == email)
            )
            if user is None:
                # Hesap yoksa da aynı maliyetli hash doğrulaması yapılır.
                check_password_hash(DUMMY_PASSWORD_HASH, password)
                errors.append('Geçersiz e-posta adresi veya parola.')
            elif not user.check_password(password):
                errors.append('Geçersiz e-posta adresi veya parola.')
            elif not user.email_verified:
                errors.append(
                    'E-posta adresiniz henüz doğrulanmamış. Doğrulama '
                    'bağlantısını yeniden gönderebilirsiniz.'
                )
            else:
                login_user(user , remember=remember)
                flash(
                    f'Hoş geldin, {user.username}!',
                    'success'
                )
                return redirect(url_for('dashboard.index'))
    return render_template('auth/login.html' , errors = errors , email = email)


@auth_bp.route('/verify-email/<token>')
def verify_email(token):
    user = verify_email_verification_token(token)

    if user is None:
        flash(
            'Doğrulama bağlantısı geçersiz veya süresi dolmuş. Yeni bir '
            'bağlantı isteyin.',
            'danger'
        )
        return redirect(url_for('auth.resend_verification'))

    if not user.email_verified:
        user.email_verified = True
        user.email_verified_at = utc_now()
        db.session.commit()
        flash('E-posta adresiniz doğrulandı. Şimdi giriş yapabilirsiniz.', 'success')
    else:
        flash('E-posta adresiniz zaten doğrulanmış.', 'info')

    return redirect(url_for('auth.login'))


@auth_bp.route('/resend-verification', methods=['GET', 'POST'])
@limiter.limit(
    lambda: current_app.config['PASSWORD_RESET_RATELIMIT'],
    methods=['POST']
)
def resend_verification():
    errors = []
    email = current_user.email if current_user.is_authenticated else ''

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()

        if not email or '@' not in email or '.' not in email.split('@')[-1]:
            errors.append('Geçerli bir e-posta adresi girin.')

        if not errors:
            user = db.session.scalar(
                db.select(User).where(User.email == email)
            )

            if user is not None and not user.email_verified:
                try:
                    send_verification_email(user)
                except Exception:
                    current_app.logger.exception(
                        'E-posta doğrulama bağlantısı yeniden gönderilemedi.'
                    )

            flash(
                'Bu adres doğrulama bekliyorsa yeni bağlantı gönderildi.',
                'success'
            )
            return redirect(url_for('auth.resend_verification'))

    return render_template(
        'auth/resend_verification.html',
        errors=errors,
        email=email
    )

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Çıkış yapıldı.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit(
    lambda: current_app.config['PASSWORD_RESET_RATELIMIT'],
    methods=['POST']
)
def forgot_password():
    errors = []
    email = ''

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()

        if not email:
            errors.append('E-posta adresi gereklidir.')
        elif '@' not in email or '.' not in email.split('@')[-1]:
            errors.append('Geçerli bir e-posta adresi girin.')

        if not errors:
            user = db.session.scalar(
                db.select(User).where(User.email == email)
            )

            if user is not None:
                token = generate_password_reset_token(user)
                reset_url = application_url(
                    'auth.reset_password',
                    token=token
                )
                expires_minutes = (
                    current_app.config['PASSWORD_RESET_MAX_AGE'] // 60
                )

                try:
                    send_email(
                        subject='FlowDesk parola sıfırlama',
                        recipient=user.email,
                        text_body=render_template(
                            'emails/password_reset.txt',
                            user=user,
                            reset_url=reset_url,
                            expires_minutes=expires_minutes
                        ),
                        html_body=render_template(
                            'emails/password_reset.html',
                            user=user,
                            reset_url=reset_url,
                            expires_minutes=expires_minutes
                        )
                    )
                except Exception:
                    current_app.logger.exception(
                        'Parola sıfırlama e-postası gönderilemedi.'
                    )

            flash(
                'Bu adresle eşleşen bir hesap varsa parola sıfırlama '
                'bağlantısı gönderildi.',
                'success'
            )
            return redirect(url_for('auth.forgot_password'))

    return render_template(
        'auth/forgot_password.html',
        errors=errors,
        email=email
    )


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = verify_password_reset_token(token)

    if user is None:
        flash(
            'Parola sıfırlama bağlantısı geçersiz veya süresi dolmuş.',
            'danger'
        )
        return redirect(url_for('auth.forgot_password'))

    errors = []

    if request.method == 'POST':
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')

        if len(password) < 8:
            errors.append('Yeni parola en az 8 karakter olmalıdır.')

        if password != password_confirm:
            errors.append('Parolalar birbiriyle eşleşmiyor.')

        if password and user.check_password(password):
            errors.append('Yeni parola önceki parolanızdan farklı olmalıdır.')

        if not errors:
            user.set_password(password)
            db.session.commit()

            if current_user.is_authenticated:
                logout_user()

            flash(
                'Parolanız yenilendi. Yeni parolanızla giriş yapabilirsiniz.',
                'success'
            )
            return redirect(url_for('auth.login'))

    return render_template(
        'auth/reset_password.html',
        errors=errors,
        token=token
    )


@auth_bp.route('/profile')
@login_required
def profile():
    return render_template(
        'auth/profile.html',
        form_username=current_user.username,
        form_email=current_user.email,
        form_phone=current_user.phone or ''
    )


@auth_bp.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip().lower()
    phone = request.form.get('phone', '').strip()
    profile_image = request.files.get('profile_image')
    errors = []

    if len(username) < 3 or len(username) > 50:
        errors.append('Kullanıcı adı 3 ile 50 karakter arasında olmalıdır.')

    if not email or '@' not in email or '.' not in email.split('@')[-1]:
        errors.append('Geçerli bir e-posta adresi girin.')
    elif len(email) > 120:
        errors.append('E-posta adresi en fazla 120 karakter olabilir.')

    if phone and not PHONE_PATTERN.fullmatch(phone):
        errors.append('Geçerli bir telefon numarası girin.')

    username_owner = db.session.scalar(
        db.select(User).where(
            User.username == username,
            User.id != current_user.id
        )
    )
    if username_owner:
        errors.append('Bu kullanıcı adı başka bir hesap tarafından kullanılıyor.')

    email_owner = db.session.scalar(
        db.select(User).where(
            User.email == email,
            User.id != current_user.id
        )
    )
    if email_owner:
        errors.append('Bu e-posta adresi başka bir hesap tarafından kullanılıyor.')

    new_image_filename = None
    if not errors and profile_image and profile_image.filename:
        try:
            new_image_filename = save_profile_image(profile_image)
        except ValueError as error:
            errors.append(str(error))

    if errors:
        return render_template(
            'auth/profile.html',
            errors=errors,
            form_username=username,
            form_email=email,
            form_phone=phone
        ), 400

    old_image_filename = current_user.profile_image
    email_changed = current_user.email != email
    current_user.username = username
    current_user.email = email
    current_user.phone = phone or None

    if email_changed:
        current_user.email_verified = False
        current_user.email_verified_at = None

    if new_image_filename:
        current_user.profile_image = new_image_filename

    db.session.commit()

    if email_changed:
        try:
            send_verification_email(current_user)
        except Exception:
            current_app.logger.exception(
                'Yeni e-posta adresi için doğrulama bağlantısı gönderilemedi.'
            )

    if new_image_filename and old_image_filename:
        delete_profile_image(old_image_filename)

    if email_changed:
        flash(
            'Profiliniz güncellendi. Yeni e-posta adresinize gönderilen '
            'bağlantıyla adresinizi doğrulayın.',
            'warning'
        )
    else:
        flash('Profil bilgileriniz başarıyla güncellendi.', 'success')
    return redirect(url_for('auth.profile'))


@auth_bp.route('/profile/photo/remove', methods=['POST'])
@login_required
def remove_profile_photo():
    old_image_filename = current_user.profile_image

    if old_image_filename:
        current_user.profile_image = None
        db.session.commit()
        delete_profile_image(old_image_filename)
        flash('Profil fotoğrafınız kaldırıldı.', 'success')
    else:
        flash('Kaldırılacak bir profil fotoğrafı bulunmuyor.', 'warning')

    return redirect(url_for('auth.profile'))


@auth_bp.route('/profile/password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')
    new_password_confirm = request.form.get('new_password_confirm', '')
    errors = []

    if not current_user.check_password(current_password):
        errors.append('Mevcut parolanız doğru değil.')

    if len(new_password) < 8:
        errors.append('Yeni parola en az 8 karakter olmalıdır.')

    if new_password != new_password_confirm:
        errors.append('Yeni parola ve parola tekrarı eşleşmiyor.')

    if current_password and new_password == current_password:
        errors.append('Yeni parola mevcut parolanızdan farklı olmalıdır.')

    if errors:
        for error in errors:
            flash(error, 'danger')
        return redirect(url_for('auth.profile') + '#password')

    current_user.set_password(new_password)
    db.session.commit()

    # Parola imzası değiştiği için tüm oturumlar düşer. Bu cihazdaki oturumu
    # yeni imzayla tazeleyip diğer cihazlardaki oturumları kapalı tutuyoruz.
    # login_user'a proxy değil gerçek nesne verilmeli; aksi halde Flask-Login
    # g._login_user'a proxy yazar ve current_user sonsuz döngüye girer.
    login_user(current_user._get_current_object(), remember=False)

    flash(
        'Parolanız başarıyla değiştirildi. Diğer cihazlardaki oturumlarınız '
        'güvenlik için kapatıldı.',
        'success'
    )
    return redirect(url_for('auth.profile') + '#password')
