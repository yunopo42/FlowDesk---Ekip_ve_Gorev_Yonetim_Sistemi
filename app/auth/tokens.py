import hashlib
import hmac

from flask import current_app
from itsdangerous import BadSignature, URLSafeTimedSerializer

from app.models import User
from extensions import db


def _password_signature(user):
    return hashlib.sha256(user.password_hash.encode('utf-8')).hexdigest()


def generate_password_reset_token(user):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(
        {
            'user_id': user.id,
            'password_signature': _password_signature(user),
        },
        salt=current_app.config['PASSWORD_RESET_SALT']
    )


def verify_password_reset_token(token):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])

    try:
        data = serializer.loads(
            token,
            salt=current_app.config['PASSWORD_RESET_SALT'],
            max_age=current_app.config['PASSWORD_RESET_MAX_AGE']
        )
    except BadSignature:
        return None

    if not isinstance(data, dict):
        return None

    user_id = data.get('user_id')
    password_signature = data.get('password_signature', '')
    if not isinstance(user_id, int) or not password_signature:
        return None

    user = db.session.get(User, user_id)
    if user is None:
        return None

    if not hmac.compare_digest(
        password_signature,
        _password_signature(user)
    ):
        return None

    return user


def generate_email_verification_token(user):
    """Kullanıcı kimliği ile mevcut e-posta adresini imzalar."""
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(
        {'user_id': user.id, 'email': user.email},
        salt=current_app.config['EMAIL_VERIFICATION_SALT']
    )


def verify_email_verification_token(token):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])

    try:
        data = serializer.loads(
            token,
            salt=current_app.config['EMAIL_VERIFICATION_SALT'],
            max_age=current_app.config['EMAIL_VERIFICATION_MAX_AGE']
        )
    except BadSignature:
        return None

    if not isinstance(data, dict):
        return None

    user_id = data.get('user_id')
    email = data.get('email')
    if not isinstance(user_id, int) or not isinstance(email, str):
        return None

    user = db.session.get(User, user_id)
    if user is None or not hmac.compare_digest(user.email, email):
        return None

    return user
