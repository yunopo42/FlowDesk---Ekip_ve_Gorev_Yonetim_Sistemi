from app.models import Team, TeamMember
from extensions import db


def test_creating_team_makes_creator_admin(
    client,
    app,
    user_factory,
    login
):
    user = user_factory()
    login(user)

    response = client.post(
        '/teams/create',
        data={
            'name': 'Yeni Ekip',
            'description': 'Test açıklaması'
        }
    )

    assert response.status_code == 302
    with app.app_context():
        team = db.session.scalar(
            db.select(Team).where(Team.name == 'Yeni Ekip')
        )
        membership = db.session.scalar(
            db.select(TeamMember).where(
                TeamMember.team_id == team.id,
                TeamMember.user_id == user.id
            )
        )
        assert membership.role == 'Admin'


def test_only_admin_can_add_member(
    client,
    app,
    user_factory,
    team_factory,
    login
):
    admin = user_factory(username='admin')
    member = user_factory(username='member')
    candidate = user_factory(
        username='candidate',
        email='candidate@example.com',
        account_type='Intern'
    )
    team = team_factory(admin, [(member, 'Member')])

    login(member)
    forbidden = client.post(
        f'/teams/{team.id}/members/add',
        data={'email': candidate.email}
    )
    assert forbidden.status_code == 403

    login(admin)
    added = client.post(
        f'/teams/{team.id}/members/add',
        data={'email': candidate.email}
    )
    assert added.status_code == 302

    with app.app_context():
        membership = db.session.scalar(
            db.select(TeamMember).where(
                TeamMember.team_id == team.id,
                TeamMember.user_id == candidate.id
            )
        )
        assert membership is not None
        assert membership.role == 'Intern'


def test_non_member_cannot_view_team(
    client,
    user_factory,
    team_factory,
    login
):
    admin = user_factory()
    outsider = user_factory()
    team = team_factory(admin)
    login(outsider)

    assert client.get(f'/teams/{team.id}').status_code == 404


def test_admin_cannot_remove_or_demote_self(
    client,
    app,
    user_factory,
    team_factory,
    login
):
    admin = user_factory()
    team = team_factory(admin)
    with app.app_context():
        membership = db.session.scalar(
            db.select(TeamMember).where(
                TeamMember.team_id == team.id,
                TeamMember.user_id == admin.id
            )
        )
        membership_id = membership.id

    login(admin)
    demote = client.post(
        f'/teams/{team.id}/members/{membership_id}/role',
        data={'role': 'Member'}
    )
    remove = client.post(
        f'/teams/{team.id}/members/{membership_id}/remove'
    )
    assert demote.status_code == 302
    assert remove.status_code == 302

    with app.app_context():
        membership = db.session.get(TeamMember, membership_id)
        assert membership is not None
        assert membership.role == 'Admin'


def test_intern_cannot_create_team(
    client,
    user_factory,
    login
):
    intern = user_factory(account_type='Intern')
    login(intern)

    response = client.post(
        '/teams/create',
        data={'name': 'Yetkisiz Ekip', 'description': ''}
    )

    assert response.status_code == 403


def test_admin_can_remove_member(
    client,
    app,
    user_factory,
    team_factory,
    login
):
    admin = user_factory()
    member = user_factory()
    team = team_factory(admin, [(member, 'Member')])
    with app.app_context():
        membership = db.session.scalar(
            db.select(TeamMember).where(
                TeamMember.team_id == team.id,
                TeamMember.user_id == member.id
            )
        )
        membership_id = membership.id

    login(admin)
    response = client.post(
        f'/teams/{team.id}/members/{membership_id}/remove'
    )
    assert response.status_code == 302

    with app.app_context():
        assert db.session.get(TeamMember, membership_id) is None


def test_personnel_can_be_added_as_team_member(
    client,
    user_factory,
    team_factory,
    login
):
    mentor = user_factory(username='team_admin')
    personnel = user_factory(
        username='other_personnel',
        email='personnel@example.com',
        account_type='Personnel'
    )
    team = team_factory(mentor)
    login(mentor)

    response = client.post(
        f'/teams/{team.id}/members/add',
        data={'email': personnel.email}
    )

    assert response.status_code == 302
    membership = db.session.scalar(
        db.select(TeamMember).where(
            TeamMember.team_id == team.id,
            TeamMember.user_id == personnel.id
        )
    )
    assert membership is not None
    assert membership.role == 'Member'
