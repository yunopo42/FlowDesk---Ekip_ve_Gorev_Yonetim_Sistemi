from datetime import datetime, timedelta


def test_dashboard_statistics_are_calculated_from_user_teams(
    client,
    user_factory,
    team_factory,
    task_factory,
    login,
    captured_templates
):
    admin = user_factory()
    team = team_factory(admin)
    task_factory(
        team,
        admin,
        title='Yapılacak görev',
        status='Todo',
        priority='High',
        due_date=datetime.now() + timedelta(days=2)
    )
    task_factory(
        team,
        admin,
        title='Devam eden görev',
        status='In Progress',
        priority='Medium'
    )
    task_factory(
        team,
        admin,
        title='Tamamlanan görev',
        status='Done',
        priority='Low',
        due_date=datetime.now() - timedelta(days=1)
    )
    task_factory(
        team,
        admin,
        title='Geciken görev',
        status='Todo',
        priority='High',
        due_date=datetime.now() - timedelta(days=1)
    )
    login(admin)

    response = client.get('/')

    assert response.status_code == 200
    assert captured_templates
    template, context = captured_templates[-1]
    assert template.name == 'dashboard/index.html'
    assert context['statistics'] == {
        'total': 4,
        'todo': 2,
        'in_progress': 1,
        'review_pending': 0,
        'revision_requested': 0,
        'done': 1,
        'overdue': 1,
    }
    assert context['priority_statistics'] == {
        'low': 1,
        'medium': 1,
        'high': 2,
    }
