import os
from dotenv import load_dotenv

# config.py dosyasının bulunduğu klasörün yolunu alıyoruz
basedir = os.path.abspath(os.path.dirname(__file__))

# .env dosyasının tam yolunu belirterek yüklenmesini garanti ediyoruz
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    # Flask güvenlik anahtarı
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'cok-gizli-bir-anahtar'
    
    # SQLAlchemy ayarları
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(basedir, 'flowdesk.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False