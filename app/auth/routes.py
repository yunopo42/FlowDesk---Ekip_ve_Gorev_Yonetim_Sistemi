from flask import flash , redirect, render_template , request , url_for
from flask_login import login_required,login_user,logout_user
from app.auth import auth_bp
from app.models import User
from extensions import db

@auth_bp.route('/register' , methods = ['GET' , 'POST'])
def register():
    errors = []
    username = ''
    email = ''

    if request.method == 'POST' :
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
                email = email
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash(
                'Hesabınız başarıyla oluşturuldu. Şimdi giriş yapabilirsiniz.',
                'success'
            )
            return redirect(url_for('auth.login'))
        
        return render_template(
            'auth/register.html',
            errors = errors,
            username = username,
            email = email
            )
    return render_template('auth/register.html')


@auth_bp.route('/login' , methods = ['GET' , 'POST'])
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
            if user is None or not user.check_password(password):
                errors.append('Geçersiz e-posta adresi veya parola.')
            else:
                login_user(user , remember=remember)
                flash(
                    f'Hoş geldin, {user.username}!',
                    'success'
                )
                return redirect(url_for('dashboard.index'))
    return render_template('auth/login.html' , errors = errors , email = email)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Çıkış yapıldı.', 'success')
    return redirect(url_for('auth.login'))