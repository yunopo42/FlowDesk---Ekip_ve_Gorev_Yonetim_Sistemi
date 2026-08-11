import pytest

from app import create_app
from config import Config


def test_custom_404_page_is_rendered(client):
    response = client.get('/olmayan-bir-sayfa')

    assert response.status_code == 404
    assert 'Aradığınız içerik burada değil' in response.get_data(
        as_text=True
    )


def test_custom_403_page_is_rendered(
    client,
    user_factory,
    team_factory,
    login
):
    admin = user_factory()
    member = user_factory()
    team = team_factory(admin, [(member, 'Member')])
    login(member)

    response = client.get(f'/teams/{team.id}/members/add')

    assert response.status_code == 403
    assert 'Bu işlem için yetkiniz yok' in response.get_data(as_text=True)


def test_custom_413_page_is_rendered(client, app):
    app.config['MAX_CONTENT_LENGTH'] = 200

    response = client.post(
        '/auth/register/intern',
        data={
            'username': 'large_request',
            'email': 'large@example.com',
            'password': 'x' * 1000,
            'password_confirm': 'x' * 1000
        }
    )

    assert response.status_code == 413
    assert 'Yükleme sınırı aşıldı' in response.get_data(as_text=True)


def test_custom_500_page_is_rendered(client, app):
    app.config['PROPAGATE_EXCEPTIONS'] = False

    def raise_test_error():
        raise RuntimeError('Yalnızca otomatik test için oluşturulan hata')

    app.add_url_rule('/_test/500', view_func=raise_test_error)
    response = client.get('/_test/500')

    assert response.status_code == 500
    body = response.get_data(as_text=True)
    assert 'Beklenmeyen bir sorun oluştu' in body
    assert 'Yalnızca otomatik test' not in body


def test_security_headers_are_added(client):
    response = client.get('/auth/login')

    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    assert response.headers['X-Frame-Options'] == 'SAMEORIGIN'
    assert response.headers['Referrer-Policy'] == (
        'strict-origin-when-cross-origin'
    )
    assert response.headers['Permissions-Policy'] == (
        'camera=(), microphone=(), geolocation=()'
    )

    secure_response = client.get(
        '/auth/login',
        base_url='https://localhost/'
    )
    assert 'max-age=31536000' in secure_response.headers[
        'Strict-Transport-Security'
    ]


def test_session_and_remember_cookies_are_hardened(
    client,
    app,
    user_factory
):
    user_factory(
        email='cookie@example.com',
        password='Password123'
    )

    response = client.post(
        '/auth/login',
        data={
            'email': 'cookie@example.com',
            'password': 'Password123',
            'remember': 'on'
        }
    )

    cookies = response.headers.getlist('Set-Cookie')
    session_cookie = next(
        cookie for cookie in cookies if cookie.startswith('session=')
    )
    remember_cookie = next(
        cookie for cookie in cookies if cookie.startswith('remember_token=')
    )

    assert 'HttpOnly' in session_cookie
    assert 'SameSite=Lax' in session_cookie
    assert 'HttpOnly' in remember_cookie
    assert 'SameSite=Lax' in remember_cookie
    assert app.config['REMEMBER_COOKIE_DURATION'].days == 14
    assert Config.SESSION_PROTECTION == 'strong'


def test_application_refuses_to_start_without_secret_key():
    class MissingSecretConfig(Config):
        TESTING = True
        SECRET_KEY = None

    with pytest.raises(RuntimeError, match='SECRET_KEY bulunamadı'):
        create_app(MissingSecretConfig)
