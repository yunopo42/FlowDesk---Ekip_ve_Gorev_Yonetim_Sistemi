import re

from app.auth.tokens import (
    generate_password_reset_token,
    verify_password_reset_token,
)
from app.models import User
from extensions import db


GENERIC_MESSAGE = (
    'Bu adresle eşleşen bir hesap varsa parola sıfırlama '
    'bağlantısı gönderildi.'
)


def request_reset(client, email):
    return client.post(
        '/auth/forgot-password',
        data={'email': email},
        follow_redirects=True
    )


def token_from_outbox(app):
    message = app.extensions['mail_outbox'][-1]
    match = re.search(
        r'/auth/reset-password/([^\s]+)',
        message['text_body']
    )
    assert match is not None
    return match.group(1)


def test_forgot_password_does_not_reveal_if_account_exists(
    client,
    app,
    user_factory
):
    user_factory(email='known@example.com')

    known = request_reset(client, 'known@example.com')
    unknown = request_reset(client, 'unknown@example.com')

    assert known.status_code == 200
    assert unknown.status_code == 200
    assert GENERIC_MESSAGE in known.get_data(as_text=True)
    assert GENERIC_MESSAGE in unknown.get_data(as_text=True)
    assert 'kayıtlı kullanıcı bulunamadı' not in unknown.get_data(as_text=True)
    assert len(app.extensions['mail_outbox']) == 1
    assert app.extensions['mail_outbox'][0]['recipient'] == (
        'known@example.com'
    )
    assert app.config['APP_BASE_URL'] in (
        app.extensions['mail_outbox'][0]['text_body']
    )


def test_valid_reset_link_changes_password_and_becomes_unusable(
    client,
    app,
    user_factory
):
    user = user_factory(
        email='reset@example.com',
        password='OldPassword123'
    )
    request_reset(client, user.email)
    token = token_from_outbox(app)

    page = client.get(f'/auth/reset-password/{token}')
    assert page.status_code == 200
    assert 'Yeni parolanızı oluşturun' in page.get_data(as_text=True)

    response = client.post(
        f'/auth/reset-password/{token}',
        data={
            'password': 'NewPassword123',
            'password_confirm': 'NewPassword123'
        }
    )
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/auth/login')

    with app.app_context():
        updated = db.session.get(User, user.id)
        assert not updated.check_password('OldPassword123')
        assert updated.check_password('NewPassword123')
        assert verify_password_reset_token(token) is None

    reused = client.get(f'/auth/reset-password/{token}')
    assert reused.status_code == 302
    assert reused.headers['Location'].endswith('/auth/forgot-password')


def test_tampered_reset_token_is_rejected(client):
    response = client.get('/auth/reset-password/gecersiz-token')

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/auth/forgot-password')


def test_expired_reset_token_is_rejected(app, user_factory):
    user = user_factory()
    token = generate_password_reset_token(user)
    app.config['PASSWORD_RESET_MAX_AGE'] = -1

    assert verify_password_reset_token(token) is None


def test_reset_password_validation_keeps_valid_token(
    client,
    app,
    user_factory
):
    user = user_factory(
        email='validation@example.com',
        password='OldPassword123'
    )
    request_reset(client, user.email)
    token = token_from_outbox(app)

    response = client.post(
        f'/auth/reset-password/{token}',
        data={
            'password': 'short',
            'password_confirm': 'different'
        }
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'en az 8 karakter' in body
    assert 'birbiriyle eşleşmiyor' in body

    with app.app_context():
        assert db.session.get(User, user.id).check_password(
            'OldPassword123'
        )
        assert verify_password_reset_token(token) is not None


def test_mail_failure_does_not_reveal_account(
    client,
    user_factory,
    monkeypatch
):
    user_factory(email='mail-error@example.com')

    def fail_to_send(**kwargs):
        raise OSError('SMTP test hatası')

    monkeypatch.setattr(
        'app.auth.routes.send_email',
        fail_to_send
    )
    response = request_reset(client, 'mail-error@example.com')

    assert response.status_code == 200
    assert GENERIC_MESSAGE in response.get_data(as_text=True)
    assert 'SMTP test hatası' not in response.get_data(as_text=True)
