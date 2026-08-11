import os

from app import create_app

app = create_app()

if __name__ == '__main__':
    # Port ve hata ayıklama ayarları ortam değişkeninden okunur; böylece
    # aynı makinede birden fazla örnek çalıştırılabilir.
    app.run(
        host=os.environ.get('HOST', '127.0.0.1'),
        port=int(os.environ.get('PORT', '5000')),
        debug=os.environ.get('FLASK_DEBUG', '').lower() in {'1', 'true', 'on'}
    )
