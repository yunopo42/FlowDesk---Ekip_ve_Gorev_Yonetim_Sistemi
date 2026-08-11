from datetime import datetime, timezone

import pytest
from flask import g, template_rendered
from flask.testing import FlaskClient
from sqlalchemy.pool import StaticPool
from werkzeug.security import generate_password_hash

import app.models.user as user_model
from app import create_app
from app.models import Task, Team, TeamMember, User
from config import Config
from extensions import db


class IsolatedClient(FlaskClient):
    """Her istek öncesi Flask-Login'in kullanıcı önbelleğini temizler.

    Testlerde tek bir app context açık tutulduğu için `g` istekler arasında
    yaşamaya devam eder. Flask-Login kullanıcıyı `g._login_user` içinde
    önbelleğe aldığından, önbellek temizlenmezse oturum çerezi yeniden
    doğrulanmaz ve testler gerçek davranışı ölçmez. Uygulama çalışırken her
    istek kendi app context'ini aldığı için böyle bir önbellek oluşmaz.
    """

    def open(self, *args, **kwargs):
        g.pop('_login_user', None)
        return super().open(*args, **kwargs)


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = 'flowdesk-test-secret'
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {'check_same_thread': False},
        'poolclass': StaticPool,
    }
    RATELIMIT_ENABLED = False
    WTF_CSRF_ENABLED = False
    SESSION_PROTECTION = None


@pytest.fixture
def app(tmp_path, monkeypatch, request):
    def fast_password_hash(password):
        return generate_password_hash(
            password,
            method='pbkdf2:sha256:10'
        )

    monkeypatch.setattr(
        user_model,
        'generate_password_hash',
        fast_password_hash
    )

    # Her test kendi config sınıfını alır; ayarlar testler arasında sızmaz.
    class CaseConfig(TestConfig):
        PROFILE_IMAGE_UPLOAD_FOLDER = str(tmp_path / 'profile-images')

    # Rate limit varsayılan olarak kapalıdır. Sayaçları test edecek testler
    # kendini @pytest.mark.ratelimit ile işaretler; Limiter deposu yalnızca
    # eklenti açıkken kurulduğu için bu ayar create_app'ten önce verilmeli.
    if request.node.get_closest_marker('ratelimit'):
        CaseConfig.RATELIMIT_ENABLED = True

    application = create_app(CaseConfig)
    application.test_client_class = IsolatedClient
    context = application.app_context()
    context.push()

    db.create_all()

    yield application

    db.session.remove()
    db.drop_all()
    context.pop()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def user_factory(app):
    counter = 0

    def create_user(
        username=None,
        email=None,
        password='Password123',
        account_type='Personnel'
    ):
        nonlocal counter
        counter += 1
        user = User(
            username=username or f'user_{counter}',
            email=email or f'user_{counter}@example.com',
            account_type=account_type
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user

    return create_user


@pytest.fixture
def team_factory(app):
    counter = 0

    def create_team(admin, members=None, name=None):
        nonlocal counter
        counter += 1
        team = Team(
            name=name or f'Test Ekibi {counter}',
            description='Otomatik test ekibi'
        )
        db.session.add(team)
        admin.account_type = 'Personnel'
        db.session.flush()
        db.session.add(
            TeamMember(
                team_id=team.id,
                user_id=admin.id,
                role='Admin'
            )
        )

        for user, role in members or []:
            user.account_type = (
                'Intern' if role == 'Intern' else 'Personnel'
            )
            db.session.add(
                TeamMember(
                    team_id=team.id,
                    user_id=user.id,
                    role=role
                )
            )

        db.session.commit()
        return team

    return create_team


@pytest.fixture
def task_factory(app):
    counter = 0

    def create_task(
        team,
        creator,
        assignee=None,
        title=None,
        priority='Medium',
        status='Todo',
        due_date=None
    ):
        nonlocal counter
        counter += 1
        task = Task(
            title=title or f'Test Görevi {counter}',
            description='Otomatik test görevi',
            priority=priority,
            status=status,
            due_date=due_date,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            team_id=team.id,
            created_by_id=creator.id,
            assigned_to_id=assignee.id if assignee else None
        )
        db.session.add(task)
        db.session.commit()
        return task

    return create_task


@pytest.fixture
def login(client):
    def login_as(user):
        with client.session_transaction() as session:
            # Oturum kimliği parola imzasını da taşır (User.get_id).
            session['_user_id'] = user.get_id()
            session['_fresh'] = True
        g.pop('_login_user', None)

    return login_as


@pytest.fixture
def captured_templates(app):
    recorded = []

    def record(sender, template, context, **extra):
        recorded.append((template, context))

    template_rendered.connect(record, app)
    yield recorded
    template_rendered.disconnect(record, app)
