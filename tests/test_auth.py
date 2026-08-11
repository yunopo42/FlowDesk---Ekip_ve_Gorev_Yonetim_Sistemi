from app.models import User
from extensions import db


def test_anonymous_user_is_redirected_to_login(client):
    response = client.get('/')

    assert response.status_code == 302
    assert '/auth/login' in response.headers['Location']


def test_login_offers_separate_personnel_and_intern_registration(client):
    response = client.get('/auth/login')
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert '/auth/register/personnel' in body
    assert '/auth/register/intern' in body
    assert 'Personel Kaydı' in body
    assert 'Stajyer Kaydı' in body


def test_intern_can_register(client, app):
    response = client.post(
        '/auth/register/intern',
        data={
            'username': 'new_user',
            'email': 'new@example.com',
            'password': 'Password123',
            'password_confirm': 'Password123',
        }
    )

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/auth/login')

    with app.app_context():
        user = db.session.scalar(
            db.select(User).where(User.email == 'new@example.com')
        )
        assert user is not None
        assert user.check_password('Password123')
        assert user.password_hash != 'Password123'
        assert user.email_verified is False
        assert user.account_type == 'Intern'
        assert len(app.extensions['mail_outbox']) == 1


def test_personnel_can_register(client, app):
    response = client.post(
        '/auth/register/personnel',
        data={
            'username': 'new_mentor',
            'email': 'mentor@example.com',
            'password': 'Password123',
            'password_confirm': 'Password123',
        }
    )

    assert response.status_code == 302
    with app.app_context():
        user = db.session.scalar(
            db.select(User).where(User.email == 'mentor@example.com')
        )
        assert user.account_type == 'Personnel'


def test_duplicate_registration_is_rejected(client, user_factory):
    user_factory(username='existing', email='existing@example.com')

    response = client.post(
        '/auth/register/intern',
        data={
            'username': 'existing',
            'email': 'existing@example.com',
            'password': 'Password123',
            'password_confirm': 'Password123',
        }
    )

    assert response.status_code == 200
    assert 'daha önce kullanılmış' in response.get_data(as_text=True)


def test_user_can_login_and_invalid_password_is_rejected(
    client,
    user_factory
):
    user_factory(
        username='login_user',
        email='login@example.com',
        password='CorrectPassword123'
    )

    invalid = client.post(
        '/auth/login',
        data={
            'email': 'login@example.com',
            'password': 'wrong-password'
        }
    )
    assert invalid.status_code == 200
    assert 'Geçersiz e-posta adresi veya parola' in invalid.get_data(
        as_text=True
    )

    valid = client.post(
        '/auth/login',
        data={
            'email': 'login@example.com',
            'password': 'CorrectPassword123'
        }
    )
    assert valid.status_code == 302
    assert valid.headers['Location'].endswith('/')
