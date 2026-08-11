import os
from datetime import timedelta

from dotenv import load_dotenv

# config.py dosyasının bulunduğu klasörün yolunu alıyoruz
basedir = os.path.abspath(os.path.dirname(__file__))

# .env dosyasının tam yolunu belirterek yüklenmesini garanti ediyoruz
load_dotenv(os.path.join(basedir, '.env'))


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}

class Config:
    # Güvenlik anahtarı yalnızca ortam değişkeninden alınır.
    SECRET_KEY = os.environ.get('SECRET_KEY')

    # Session ve "beni hatırla" cookie güvenliği.
    COOKIE_SECURE = env_bool('COOKIE_SECURE', False)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = COOKIE_SECURE
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_SECURE = COOKIE_SECURE
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    SESSION_PROTECTION = 'strong'

    # Parola sıfırlama bağlantıları 60 dakika geçerlidir.
    PASSWORD_RESET_MAX_AGE = 60 * 60
    PASSWORD_RESET_SALT = os.environ.get(
        'PASSWORD_RESET_SALT',
        'flowdesk-password-reset'
    )
    EMAIL_VERIFICATION_MAX_AGE = 24 * 60 * 60
    EMAIL_VERIFICATION_SALT = os.environ.get(
        'EMAIL_VERIFICATION_SALT',
        'flowdesk-email-verification'
    )
    APP_BASE_URL = os.environ.get(
        'APP_BASE_URL',
        'http://127.0.0.1:5000'
    ).rstrip('/')

    # SMTP e-posta ayarları. Sunucu tanımlı değilse geliştirme kutusu kullanılır.
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
    MAIL_USE_TLS = env_bool('MAIL_USE_TLS', True)
    MAIL_USE_SSL = env_bool('MAIL_USE_SSL', False)
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get(
        'MAIL_DEFAULT_SENDER',
        'FlowDesk <noreply@flowdesk.local>'
    )
    MAIL_SUPPRESS_SEND = env_bool(
        'MAIL_SUPPRESS_SEND',
        not bool(MAIL_SERVER)
    )
    
    # SQLAlchemy ayarları
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(basedir, 'flowdesk.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Geliştirme ortamında rate-limit sayaçlarını bellekte tutar.
    # Canlı ortamda bu değer Redis bağlantısıyla değiştirilecektir.
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI') or 'memory://'

    # Kimlik doğrulama uçlarının deneme sınırları. Giriş ve parola sıfırlama
    # uçları kaba kuvvet saldırılarına açık olduğu için ayrı ayrı sınırlanır.
    LOGIN_RATELIMIT = os.environ.get(
        'LOGIN_RATELIMIT',
        '10 per 15 minutes'
    )
    REGISTER_RATELIMIT = os.environ.get(
        'REGISTER_RATELIMIT',
        '10 per hour'
    )
    PASSWORD_RESET_RATELIMIT = os.environ.get(
        'PASSWORD_RESET_RATELIMIT',
        '5 per hour'
    )

    # Tailwind CDN dışında hiçbir dış kaynağa izin verilmez. Tailwind'in
    # tarayıcı derlemesi stilleri çalışma anında <style> olarak eklediği için
    # style-src 'unsafe-inline' gerekir; script-src inline betiğe izin vermez.
    CONTENT_SECURITY_POLICY = os.environ.get(
        'CONTENT_SECURITY_POLICY',
        "default-src 'self'; "
        "script-src 'self' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self' data:; "
        "connect-src 'self' https://cdn.jsdelivr.net; "
        "form-action 'self'; "
        "frame-ancestors 'self'; "
        "base-uri 'self'; "
        "object-src 'none'"
    )

    # Profil fotoğrafları en fazla 5 MB olabilir.
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
    PROFILE_IMAGE_UPLOAD_FOLDER = os.path.join(
        basedir,
        'app',
        'static',
        'uploads',
        'profiles'
    )
