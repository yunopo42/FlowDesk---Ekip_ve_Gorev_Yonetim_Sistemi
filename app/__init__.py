from flask import Flask
from config import Config
from extensions import db , login_manager , limiter
#oluşturduğumuz eklentileri dosyalardan çektim

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class) #config.py deki ayarları uygulamaya yükledik
    from app import models
    db.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)

    from app.models import User, Team, TeamMember, Task, Comment, Activity

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    login_manager.login_view = 'auth.login'
    login_manager.login_message = "Bu sayfayı görüntülemek için lütfen giriş yapın."
    login_manager.login_message_category = "warning"

    from app.dashboard import dashboard_bp
    from app.auth import auth_bp
    from app.teams import teams_bp
    from app.tasks import tasks_bp
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(teams_bp)
    app.register_blueprint(tasks_bp)
    
    return app

