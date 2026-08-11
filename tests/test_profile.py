from io import BytesIO
from pathlib import Path

from PIL import Image

from app.models import User
from extensions import db


def test_user_can_update_profile_and_phone(
    client,
    app,
    user_factory,
    login
):
    user = user_factory(
        username='old_name',
        email='old@example.com'
    )
    login(user)

    response = client.post(
        '/auth/profile/update',
        data={
            'username': 'new_name',
            'email': 'new@example.com',
            'phone': '+90 555 123 45 67'
        }
    )

    assert response.status_code == 302

    with app.app_context():
        updated = db.session.get(User, user.id)
        assert updated.username == 'new_name'
        assert updated.email == 'new@example.com'
        assert updated.phone == '+90 555 123 45 67'
        assert updated.email_verified is False
        assert len(app.extensions['mail_outbox']) == 1


def test_duplicate_profile_information_is_rejected(
    client,
    user_factory,
    login
):
    user = user_factory(username='first_user', email='first@example.com')
    user_factory(username='second_user', email='second@example.com')
    login(user)

    response = client.post(
        '/auth/profile/update',
        data={
            'username': 'second_user',
            'email': 'second@example.com',
            'phone': ''
        }
    )

    assert response.status_code == 400
    body = response.get_data(as_text=True)
    assert 'başka bir hesap tarafından kullanılıyor' in body


def test_profile_photo_is_processed_and_can_be_removed(
    client,
    app,
    user_factory,
    login
):
    user = user_factory()
    login(user)
    source = BytesIO()
    Image.new('RGB', (900, 600), '#4f46e5').save(source, format='PNG')
    source.seek(0)

    response = client.post(
        '/auth/profile/update',
        data={
            'username': user.username,
            'email': user.email,
            'phone': '',
            'profile_image': (source, 'avatar.png')
        },
        content_type='multipart/form-data'
    )
    assert response.status_code == 302

    with app.app_context():
        updated = db.session.get(User, user.id)
        filename = updated.profile_image
        image_path = Path(
            app.config['PROFILE_IMAGE_UPLOAD_FOLDER']
        ) / filename
        assert filename.endswith('.webp')
        assert image_path.is_file()
        with Image.open(image_path) as stored:
            assert stored.size == (512, 512)
            assert stored.format == 'WEBP'

    removed = client.post('/auth/profile/photo/remove')
    assert removed.status_code == 302

    with app.app_context():
        assert db.session.get(User, user.id).profile_image is None
    assert not image_path.exists()


def test_password_change_requires_current_password(
    client,
    app,
    user_factory,
    login
):
    user = user_factory(password='OldPassword123')
    login(user)

    client.post(
        '/auth/profile/password',
        data={
            'current_password': 'wrong-password',
            'new_password': 'NewPassword123',
            'new_password_confirm': 'NewPassword123'
        }
    )

    with app.app_context():
        assert db.session.get(User, user.id).check_password(
            'OldPassword123'
        )

    response = client.post(
        '/auth/profile/password',
        data={
            'current_password': 'OldPassword123',
            'new_password': 'NewPassword123',
            'new_password_confirm': 'NewPassword123'
        }
    )
    assert response.status_code == 302

    with app.app_context():
        assert db.session.get(User, user.id).check_password(
            'NewPassword123'
        )
