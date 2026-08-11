import hashlib

from extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash , check_password_hash

from app.models.base import utc_now

class User(db.Model , UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer , primary_key=True)
    username = db.Column(db.String(50) , unique = True , nullable = False)
    email = db.Column(db.String(120) , unique = True , nullable = False)
    # Mevcut kullanıcılar ile yönetim/test tarafında oluşturulan hesaplar
    # doğrulanmış kabul edilir. Normal kayıt akışı bu değeri False yapar.
    email_verified = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
        server_default=db.true()
    )
    email_verified_at = db.Column(db.DateTime, nullable=True)
    account_type = db.Column(
        db.String(20),
        nullable=False,
        default='Intern',
        server_default='Intern'
    )
    phone = db.Column(db.String(20), nullable=True)
    profile_image = db.Column(db.String(255), nullable=True)
    password_hash = db.Column(db.String(255) , nullable = False)
    created_at = db.Column(db.DateTime, default=utc_now)
    
    #şifreyi hashleme
    def set_password(self , password):
        self.password_hash = generate_password_hash(password)

    #şifre kotnrol
    def check_password(self , password):
        return check_password_hash(self.password_hash , password)

    @property
    def session_signature(self):
        """Parola hash'inden türeyen, oturum çerezine gömülen kısa imza.

        Parola her değiştiğinde bu imza da değişir. Böylece eski oturum ve
        "beni hatırla" çerezleri kendiliğinden geçersiz olur.
        """
        return hashlib.sha256(
            self.password_hash.encode('utf-8')
        ).hexdigest()[:16]

    def get_id(self):
        """Flask-Login'in çereze yazdığı kimlik: id ve parola imzası."""
        return f'{self.id}|{self.session_signature}'

    @property
    def is_personnel(self):
        return self.account_type == 'Personnel'

    @property
    def is_intern(self):
        return self.account_type == 'Intern'

    def __repr__(self):
        return f'<User {self.username}>'
