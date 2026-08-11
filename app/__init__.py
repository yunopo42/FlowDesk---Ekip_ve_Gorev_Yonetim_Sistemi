import hmac

from flask import Flask, render_template, request
from flask_wtf.csrf import CSRFError
from config import Config
from extensions import csrf, db, login_manager, limiter, migrate
#oluşturduğumuz eklentileri dosyalardan çektim

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class) #config.py deki ayarları uygulamaya yükledik

    if not app.config.get('SECRET_KEY'):
        raise RuntimeError(
            'SECRET_KEY bulunamadı. .env dosyasına güçlü ve benzersiz '
            'bir SECRET_KEY ekleyin.'
        )

    from app import models
    db.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        return render_template(
            'errors/csrf.html',
            reason=error.description
        ), 400

    @app.errorhandler(403)
    def forbidden(error):
        return render_template(
            'errors/error.html',
            code=403,
            label='Erişim reddedildi',
            title='Bu işlem için yetkiniz yok',
            message=(
                'Bu sayfayı görüntülemek veya bu işlemi yapmak için '
                'gerekli ekip rolüne sahip değilsiniz.'
            ),
            icon='🔒',
            color='red'
        ), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template(
            'errors/error.html',
            code=404,
            label='Sayfa bulunamadı',
            title='Aradığınız içerik burada değil',
            message=(
                'Bağlantı değişmiş, içerik kaldırılmış veya bu kaynağa '
                'erişiminiz bulunmuyor olabilir.'
            ),
            icon='🧭',
            color='indigo'
        ), 404

    @app.errorhandler(413)
    def file_too_large(error):
        return render_template(
            'errors/error.html',
            code=413,
            label='Dosya çok büyük',
            title='Yükleme sınırı aşıldı',
            message=(
                'Yüklediğiniz dosya 5 MB sınırını aşıyor. Daha küçük '
                'bir görsel seçip yeniden deneyin.'
            ),
            icon='📦',
            color='amber'
        ), 413

    @app.errorhandler(429)
    def too_many_requests(error):
        return render_template(
            'errors/error.html',
            code=429,
            label='Çok fazla deneme',
            title='Bir süre beklemeniz gerekiyor',
            message=(
                getattr(error, 'description', None)
                or 'Kısa sürede çok fazla istek gönderdiniz. Güvenliğiniz '
                'için bu işlem geçici olarak durduruldu. Bir süre sonra '
                'yeniden deneyin.'
            ),
            icon='⏳',
            color='amber'
        ), 429

    @app.errorhandler(500)
    def internal_server_error(error):
        db.session.rollback()
        return render_template(
            'errors/error.html',
            code=500,
            label='Sunucu hatası',
            title='Beklenmeyen bir sorun oluştu',
            message=(
                'İşleminiz tamamlanamadı. Bir süre sonra yeniden deneyin. '
                'Sorun devam ederse sistem yöneticisine bildirin.'
            ),
            icon='🛠️',
            color='slate'
        ), 500

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        response.headers.setdefault(
            'Referrer-Policy',
            'strict-origin-when-cross-origin'
        )
        response.headers.setdefault(
            'Permissions-Policy',
            'camera=(), microphone=(), geolocation=()'
        )
        response.headers.setdefault(
            'Content-Security-Policy',
            app.config['CONTENT_SECURITY_POLICY']
        )
        response.headers.setdefault(
            'Cross-Origin-Opener-Policy',
            'same-origin'
        )

        if request.is_secure:
            response.headers.setdefault(
                'Strict-Transport-Security',
                'max-age=31536000; includeSubDomains'
            )

        return response

    from app.models import (
        Activity,
        Comment,
        DailyLog,
        Internship,
        INTERNSHIP_STATUS_LABELS,
        REVIEW_STATUS_LABELS,
        Task,
        TASK_PRIORITY_LABELS,
        TASK_STATUS_LABELS,
        TaskSubmission,
        Team,
        TeamMember,
        User,
    )

    @app.context_processor
    def inject_status_labels():
        """Durum kodlarının Türkçe karşılıklarını tüm şablonlara verir."""
        return {
            'task_status_labels': TASK_STATUS_LABELS,
            'task_priority_labels': TASK_PRIORITY_LABELS,
            'internship_status_labels': INTERNSHIP_STATUS_LABELS,
            'review_status_labels': REVIEW_STATUS_LABELS,
        }

    @login_manager.user_loader
    def load_user(user_id):
        # Çerezdeki kimlik "<id>|<parola imzası>" biçimindedir. İmza mevcut
        # parola ile eşleşmezse oturum kabul edilmez; parola değiştiğinde
        # tüm eski oturumlar ve "beni hatırla" çerezleri düşer.
        identifier, _, signature = str(user_id).partition('|')

        if not identifier.isdigit():
            return None

        user = db.session.get(User, int(identifier))

        if user is None:
            return None

        if not signature or not hmac.compare_digest(
            signature,
            user.session_signature
        ):
            return None

        return user
    login_manager.login_view = 'auth.login'
    login_manager.login_message = "Bu sayfayı görüntülemek için lütfen giriş yapın."
    login_manager.login_message_category = "warning"

    from app.dashboard import dashboard_bp
    from app.auth import auth_bp
    from app.teams import teams_bp
    from app.tasks import tasks_bp
    from app.internships import internships_bp
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(teams_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(internships_bp)
    
    return app

