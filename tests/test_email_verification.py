import re

from app.auth.tokens import generate_email_verification_token
from app.models import User
from extensions import db


def verification_token_from_outbox(app):
    message = app.extensions['mail_outbox'][-1]
    match = re.search(r'/auth/verify-email/([^\s<]+)', message['text_body'])
    assert match is not None
    return match.group(1)


def test_unverified_user_cannot_login(client, user_factory):
    user = user_factory(
        email='waiting@example.com',
        password='Password123'
    )
    user.email_verified = False
    db.session.commit()

    response = client.post(
        '/auth/login',
        data={'email': user.email, 'password': 'Password123'}
    )

    assert response.status_code == 200
    assert 'henüz doğrulanmamış' in response.get_data(as_text=True)
    with client.session_transaction() as session:
        assert '_user_id' not in session


def test_valid_link_verifies_email_and_allows_login(
    client,
    app,
    user_factory
):
    user = user_factory(
        email='verify@example.com',
        password='Password123'
    )
    user.email_verified = False
    db.session.commit()

    with app.app_context():
        token = generate_email_verification_token(user)

    response = client.get(f'/auth/verify-email/{token}')
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/auth/login')

    with app.app_context():
        verified = db.session.get(User, user.id)
        assert verified.email_verified is True
        assert verified.email_verified_at is not None

    login_response = client.post(
        '/auth/login',
        data={'email': user.email, 'password': 'Password123'}
    )
    assert login_response.status_code == 302
    assert login_response.headers['Location'].endswith('/')


def test_verification_token_is_bound_to_current_email(client, app, user_factory):
    user = user_factory(email='first-address@example.com')
    user.email_verified = False
    db.session.commit()

    with app.app_context():
        token = generate_email_verification_token(user)
        user.email = 'changed-address@example.com'
        db.session.commit()

    response = client.get(f'/auth/verify-email/{token}')
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/auth/resend-verification')

    with app.app_context():
        assert db.session.get(User, user.id).email_verified is False


def test_expired_verification_token_is_rejected(client, app, user_factory):
    user = user_factory(email='expired-verification@example.com')
    user.email_verified = False
    db.session.commit()

    with app.app_context():
        token = generate_email_verification_token(user)

    app.config['EMAIL_VERIFICATION_MAX_AGE'] = -1
    response = client.get(f'/auth/verify-email/{token}')

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/auth/resend-verification')


def test_resend_does_not_reveal_whether_account_exists(
    client,
    app,
    user_factory
):
    user = user_factory(email='resend@example.com')
    user.email_verified = False
    db.session.commit()

    known = client.post(
        '/auth/resend-verification',
        data={'email': user.email},
        follow_redirects=True
    )
    known_body = known.get_data(as_text=True)
    assert 'doğrulama bekliyorsa' in known_body
    assert len(app.extensions['mail_outbox']) == 1
    token = verification_token_from_outbox(app)
    assert token

    unknown = client.post(
        '/auth/resend-verification',
        data={'email': 'missing@example.com'},
        follow_redirects=True
    )
    unknown_body = unknown.get_data(as_text=True)
    assert 'doğrulama bekliyorsa' in unknown_body
    assert len(app.extensions['mail_outbox']) == 1


def test_resend_skips_already_verified_account(client, app, user_factory):
    user = user_factory(email='already@example.com')

    response = client.post(
        '/auth/resend-verification',
        data={'email': user.email},
        follow_redirects=True
    )

    assert response.status_code == 200
    assert 'doğrulama bekliyorsa' in response.get_data(as_text=True)
    assert app.extensions.get('mail_outbox', []) == []
