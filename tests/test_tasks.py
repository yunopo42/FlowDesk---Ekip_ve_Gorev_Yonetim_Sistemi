from datetime import datetime, timedelta

from app.models import Activity, Comment, Task
from extensions import db


def test_admin_can_create_and_assign_task(
    client,
    app,
    user_factory,
    team_factory,
    login
):
    admin = user_factory(username='admin')
    member = user_factory(username='member')
    team = team_factory(admin, [(member, 'Member')])
    login(admin)

    response = client.post(
        f'/tasks/create/{team.id}',
        data={
            'title': 'Atanmış görev',
            'description': 'Test görevi',
            'priority': 'High',
            'assigned_to_id': str(member.id),
            'due_date': (datetime.now() + timedelta(days=5))
            .date()
            .isoformat()
        }
    )
    assert response.status_code == 302

    with app.app_context():
        task = db.session.scalar(
            db.select(Task).where(Task.title == 'Atanmış görev')
        )
        assert task.assigned_to_id == member.id
        assert task.priority == 'High'
        assert task.status == 'Todo'
        activity = db.session.scalar(
            db.select(Activity).where(Activity.task_id == task.id)
        )
        assert activity.action == 'Görev oluşturuldu.'


def test_personnel_member_can_assign_task_to_another_user(
    client,
    app,
    user_factory,
    team_factory,
    login
):
    admin = user_factory(username='admin')
    first_member = user_factory(username='first_member')
    second_member = user_factory(username='second_member')
    team = team_factory(
        admin,
        [(first_member, 'Member'), (second_member, 'Member')]
    )
    login(first_member)

    response = client.post(
        f'/tasks/create/{team.id}',
        data={
            'title': 'Ekip içi atama',
            'description': '',
            'priority': 'Medium',
            'assigned_to_id': str(second_member.id),
            'due_date': (datetime.now() + timedelta(days=5))
            .date()
            .isoformat()
        }
    )
    assert response.status_code == 302

    with app.app_context():
        task = db.session.scalar(
            db.select(Task).where(Task.title == 'Ekip içi atama')
        )
        assert task is not None
        assert task.created_by_id == first_member.id
        assert task.assigned_to_id == second_member.id


def test_intern_cannot_create_task(
    client,
    user_factory,
    team_factory,
    login
):
    admin = user_factory(username='admin')
    intern = user_factory(username='intern', account_type='Intern')
    team = team_factory(admin, [(intern, 'Intern')])
    login(intern)

    response = client.post(
        f'/tasks/create/{team.id}',
        data={
            'title': 'Yetkisiz görev',
            'description': '',
            'priority': 'Medium',
            'assigned_to_id': str(intern.id),
            'due_date': (datetime.now() + timedelta(days=5))
            .date()
            .isoformat()
        }
    )

    assert response.status_code == 403
    assert db.session.scalar(
        db.select(Task).where(Task.title == 'Yetkisiz görev')
    ) is None


def test_only_admin_or_assignee_can_update_status(
    client,
    app,
    user_factory,
    team_factory,
    task_factory,
    login
):
    admin = user_factory()
    assignee = user_factory()
    other_member = user_factory()
    team = team_factory(
        admin,
        [(assignee, 'Member'), (other_member, 'Member')]
    )
    task = task_factory(team, admin, assignee=assignee)

    login(other_member)
    assert client.post(
        f'/tasks/{task.id}/status',
        data={'status': 'In Progress'}
    ).status_code == 403

    login(assignee)
    response = client.post(
        f'/tasks/{task.id}/status',
        data={'status': 'In Progress'}
    )
    assert response.status_code == 302

    with app.app_context():
        updated = db.session.get(Task, task.id)
        assert updated.status == 'In Progress'
        assert any(
            'Durum Yapılacak değerinden Devam ediyor' in activity.action
            for activity in updated.activities
        )


def test_outsider_cannot_view_task(
    client,
    user_factory,
    team_factory,
    task_factory,
    login
):
    admin = user_factory()
    outsider = user_factory()
    team = team_factory(admin)
    task = task_factory(team, admin)
    login(outsider)

    assert client.get(f'/tasks/{task.id}').status_code == 404


def test_team_member_can_comment_on_task(
    client,
    app,
    user_factory,
    team_factory,
    task_factory,
    login
):
    admin = user_factory()
    member = user_factory()
    team = team_factory(admin, [(member, 'Member')])
    task = task_factory(team, admin, assignee=member)
    login(member)

    response = client.post(
        f'/tasks/{task.id}/comments',
        data={'content': 'Görev üzerinde çalışmaya başladım.'}
    )
    assert response.status_code == 302

    with app.app_context():
        comment = db.session.scalar(
            db.select(Comment).where(Comment.task_id == task.id)
        )
        assert comment.user_id == member.id
        assert comment.content == 'Görev üzerinde çalışmaya başladım.'


def test_task_search_and_filters_only_show_matching_tasks(
    client,
    user_factory,
    team_factory,
    task_factory,
    login
):
    admin = user_factory()
    team = team_factory(admin)
    task_factory(
        team,
        admin,
        title='Önemli raporu hazırla',
        priority='High',
        status='In Progress'
    )
    task_factory(
        team,
        admin,
        title='Eski belgeleri arşivle',
        priority='Low',
        status='Done'
    )
    login(admin)

    response = client.get(
        '/tasks/?q=rapor&status=In+Progress&priority=High'
    )
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'Önemli raporu hazırla' in body
    assert 'Eski belgeleri arşivle' not in body


def test_intern_only_sees_assigned_tasks(
    client,
    user_factory,
    team_factory,
    task_factory,
    login
):
    mentor = user_factory()
    first_intern = user_factory(account_type='Intern')
    second_intern = user_factory(account_type='Intern')
    team = team_factory(
        mentor,
        [(first_intern, 'Intern'), (second_intern, 'Intern')]
    )
    own_task = task_factory(
        team,
        mentor,
        assignee=first_intern,
        title='Bana atanan görev'
    )
    other_task = task_factory(
        team,
        mentor,
        assignee=second_intern,
        title='Diğer stajyerin görevi'
    )
    login(first_intern)

    response = client.get('/tasks/')
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert own_task.title in body
    assert other_task.title not in body
    assert client.get(f'/tasks/{other_task.id}').status_code == 404
