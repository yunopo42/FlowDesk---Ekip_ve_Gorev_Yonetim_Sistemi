from datetime import date, timedelta
from decimal import Decimal

from app.models import DailyLog, Internship, TaskSubmission, TeamMember
from extensions import db


def create_internship(team, mentor, intern, **overrides):
    internship = Internship(
        team_id=team.id,
        mentor_id=mentor.id,
        intern_id=intern.id,
        company_unit=overrides.get(
            'company_unit',
            'Yazılım Geliştirme Birimi'
        ),
        internship_role=overrides.get(
            'internship_role',
            'Backend Developer Stajyeri'
        ),
        start_date=overrides.get(
            'start_date',
            date.today() - timedelta(days=5)
        ),
        end_date=overrides.get(
            'end_date',
            date.today() + timedelta(days=30)
        ),
        status=overrides.get('status', 'Active')
    )
    db.session.add(internship)
    db.session.commit()
    return internship


def test_mentor_can_create_internship(
    client,
    app,
    user_factory,
    team_factory,
    login
):
    mentor = user_factory(username='mentor')
    intern = user_factory(username='intern')
    team = team_factory(mentor, members=[(intern, 'Intern')])
    login(mentor)

    response = client.post(
        '/internships/create',
        data={
            'team_id': str(team.id),
            'intern_id': str(intern.id),
            'company_unit': 'Bilgi Teknolojileri',
            'internship_role': 'Yazılım Geliştirme Stajyeri',
            'start_date': date.today().isoformat(),
            'end_date': (date.today() + timedelta(days=20)).isoformat(),
        }
    )

    assert response.status_code == 302
    detail_response = client.get(response.headers['Location'])
    assert detail_response.status_code == 200
    assert 'Bilgi Teknolojileri' in detail_response.get_data(as_text=True)

    with app.app_context():
        internship = db.session.scalar(
            db.select(Internship).where(Internship.intern_id == intern.id)
        )
        assert internship is not None
        assert internship.mentor_id == mentor.id
        assert internship.status == 'Active'


def test_personnel_can_select_unassigned_intern_and_add_to_team(
    client,
    app,
    user_factory,
    team_factory,
    login
):
    personnel = user_factory(username='personnel')
    intern = user_factory(
        username='available_intern',
        email='available.intern@example.com',
        account_type='Intern'
    )
    team = team_factory(personnel)
    login(personnel)

    form_response = client.get('/internships/create')
    form_body = form_response.get_data(as_text=True)

    assert form_response.status_code == 200
    assert 'available_intern' in form_body
    assert 'available.intern@example.com' in form_body

    response = client.post(
        '/internships/create',
        data={
            'team_id': str(team.id),
            'intern_id': str(intern.id),
            'company_unit': 'Yazılım Geliştirme',
            'internship_role': 'Backend Stajyeri',
            'start_date': date.today().isoformat(),
            'end_date': (date.today() + timedelta(days=20)).isoformat(),
        }
    )

    assert response.status_code == 302

    with app.app_context():
        membership = db.session.scalar(
            db.select(TeamMember).where(
                TeamMember.team_id == team.id,
                TeamMember.user_id == intern.id
            )
        )
        internship = db.session.scalar(
            db.select(Internship).where(
                Internship.team_id == team.id,
                Internship.intern_id == intern.id
            )
        )

        assert membership is not None
        assert membership.role == 'Intern'
        assert internship is not None
        assert internship.mentor_id == personnel.id


def test_intern_cannot_create_internship(
    client,
    user_factory,
    team_factory,
    login
):
    mentor = user_factory()
    intern = user_factory(account_type='Intern')
    team_factory(mentor, members=[(intern, 'Intern')])
    login(intern)

    response = client.get('/internships/create')

    assert response.status_code == 403


def test_intern_can_submit_daily_log_and_mentor_can_approve(
    client,
    app,
    user_factory,
    team_factory,
    login
):
    mentor = user_factory(username='daily_mentor')
    intern = user_factory(username='daily_intern')
    team = team_factory(mentor, members=[(intern, 'Intern')])
    internship = create_internship(team, mentor, intern)
    login(intern)

    response = client.post(
        f'/internships/{internship.id}/daily-logs/new',
        data={
            'work_date': date.today().isoformat(),
            'hours': '7.5',
            'title': 'Flask yetkilendirmesi',
            'work_summary': 'Rol kontrollerini geliştirdim.',
            'learned': 'Backend yetkilendirmesini öğrendim.',
            'blockers': 'Test verisi hazırlamak zaman aldı.',
        }
    )
    assert response.status_code == 302
    detail_response = client.get(response.headers['Location'])
    assert detail_response.status_code == 200
    assert 'Flask yetkilendirmesi' in detail_response.get_data(as_text=True)

    with app.app_context():
        daily_log = db.session.scalar(db.select(DailyLog))
        assert daily_log.status == 'Submitted'
        assert daily_log.hours == Decimal('7.50')
        log_id = daily_log.id

    login(mentor)
    review = client.post(
        f'/internships/daily-logs/{log_id}/review',
        data={
            'status': 'Approved',
            'mentor_feedback': 'Çalışma yeterli.'
        }
    )
    assert review.status_code == 302

    with app.app_context():
        approved_log = db.session.get(DailyLog, log_id)
        assert approved_log.status == 'Approved'
        assert approved_log.reviewed_at is not None


def test_outsider_cannot_see_internship(
    client,
    user_factory,
    team_factory,
    login
):
    mentor = user_factory()
    intern = user_factory()
    outsider = user_factory()
    team = team_factory(mentor, members=[(intern, 'Intern')])
    internship = create_internship(team, mentor, intern)
    login(outsider)

    response = client.get(f'/internships/{internship.id}')

    assert response.status_code == 404


def test_intern_submits_task_and_mentor_requests_revision(
    client,
    app,
    user_factory,
    team_factory,
    task_factory,
    login
):
    mentor = user_factory(username='task_mentor')
    intern = user_factory(username='task_intern')
    team = team_factory(mentor, members=[(intern, 'Intern')])
    create_internship(team, mentor, intern)
    task = task_factory(team, mentor, assignee=intern)
    login(intern)

    response = client.post(
        f'/tasks/{task.id}/submissions',
        data={
            'commit_message': 'feat: görev teslimini tamamla',
            'summary': 'Görev tamamlandı ve test edildi.',
            'work_url': 'https://github.com/example/project',
            'learned': 'Flask route yapısı',
            'challenges': 'Yetki kontrolü'
        }
    )
    assert response.status_code == 302
    detail_response = client.get(response.headers['Location'])
    assert detail_response.status_code == 200
    assert 'Görev tamamlandı ve test edildi.' in detail_response.get_data(
        as_text=True
    )

    with app.app_context():
        submission = db.session.scalar(db.select(TaskSubmission))
        assert submission.status == 'Pending Review'
        assert submission.commit_message == 'feat: görev teslimini tamamla'
        assert db.session.get(type(task), task.id).status == 'Review Pending'
        submission_id = submission.id

    login(mentor)
    review = client.post(
        f'/tasks/submissions/{submission_id}/review',
        data={
            'decision': 'Revision Requested',
            'mentor_feedback': 'Bir yetki testi daha ekleyin.'
        }
    )
    assert review.status_code == 302

    with app.app_context():
        submission = db.session.get(TaskSubmission, submission_id)
        assert submission.status == 'Revision Requested'
        assert submission.task.status == 'Revision Requested'
        assert submission.reviewed_by_id == mentor.id


def test_intern_submission_is_completed_only_after_mentor_approval(
    client,
    app,
    user_factory,
    team_factory,
    task_factory,
    login
):
    mentor = user_factory(username='approval_mentor')
    intern = user_factory(username='approval_intern')
    team = team_factory(mentor, members=[(intern, 'Intern')])
    create_internship(team, mentor, intern)
    task = task_factory(team, mentor, assignee=intern)

    login(intern)
    submission_response = client.post(
        f'/tasks/{task.id}/submissions',
        data={
            'commit_message': 'feat: assigned work completed',
            'summary': 'Görevi tamamladım ve kontrollerini yaptım.',
            'work_url': 'https://github.com/example/project/commit/123',
            'learned': '',
            'challenges': ''
        }
    )

    assert submission_response.status_code == 302
    with app.app_context():
        submission = db.session.scalar(db.select(TaskSubmission))
        assert submission.status == 'Pending Review'
        assert db.session.get(type(task), task.id).status == 'Review Pending'
        submission_id = submission.id

    login(mentor)
    approval_response = client.post(
        f'/tasks/submissions/{submission_id}/review',
        data={
            'decision': 'Approved',
            'mentor_feedback': 'Çalışma kabul edildi.'
        }
    )

    assert approval_response.status_code == 302
    with app.app_context():
        approved = db.session.get(TaskSubmission, submission_id)
        assert approved.status == 'Approved'
        assert approved.task.status == 'Done'
        assert approved.reviewed_by_id == mentor.id


def test_task_creator_can_approve_even_if_internship_mentor_is_different(
    client,
    user_factory,
    team_factory,
    task_factory,
    login
):
    mentor = user_factory(username='designated_mentor')
    other_admin = user_factory(username='other_admin')
    intern = user_factory(username='protected_intern')
    team = team_factory(
        mentor,
        members=[(other_admin, 'Admin'), (intern, 'Intern')]
    )
    create_internship(team, mentor, intern)
    task = task_factory(team, other_admin, assignee=intern)

    login(intern)
    client.post(
        f'/tasks/{task.id}/submissions',
        data={
            'commit_message': 'feat: protected submission',
            'summary': 'İncelemeye hazır.',
            'work_url': 'https://github.com/example/project/pull/7',
        }
    )
    submission = db.session.scalar(db.select(TaskSubmission))

    login(other_admin)
    response = client.post(
        f'/tasks/submissions/{submission.id}/review',
        data={'decision': 'Approved', 'mentor_feedback': ''}
    )

    assert response.status_code == 302
    db.session.refresh(submission)
    assert submission.status == 'Approved'
    assert submission.task.status == 'Done'
    assert submission.reviewed_by_id == other_admin.id


def test_unrelated_personnel_cannot_approve_intern_submission(
    client,
    user_factory,
    team_factory,
    task_factory,
    login
):
    mentor = user_factory(username='submission_mentor')
    creator = user_factory(username='task_creator')
    unrelated = user_factory(username='unrelated_personnel')
    intern = user_factory(username='submission_intern')
    team = team_factory(
        mentor,
        members=[
            (creator, 'Member'),
            (unrelated, 'Member'),
            (intern, 'Intern')
        ]
    )
    create_internship(team, mentor, intern)
    task = task_factory(team, creator, assignee=intern)

    login(intern)
    client.post(
        f'/tasks/{task.id}/submissions',
        data={
            'commit_message': 'feat: review permissions',
            'summary': 'Görev incelemeye hazır.',
            'work_url': 'https://github.com/example/project/pull/8',
        }
    )
    submission = db.session.scalar(db.select(TaskSubmission))

    login(unrelated)
    response = client.post(
        f'/tasks/submissions/{submission.id}/review',
        data={'decision': 'Approved', 'mentor_feedback': ''}
    )

    assert response.status_code == 403
    db.session.refresh(submission)
    assert submission.status == 'Pending Review'
    assert submission.task.status == 'Review Pending'


def test_intern_cannot_mark_internship_task_done_directly(
    client,
    app,
    user_factory,
    team_factory,
    task_factory,
    login
):
    mentor = user_factory()
    intern = user_factory()
    team = team_factory(mentor, members=[(intern, 'Intern')])
    create_internship(team, mentor, intern)
    task = task_factory(team, mentor, assignee=intern)
    login(intern)

    response = client.post(
        f'/tasks/{task.id}/status',
        data={'status': 'Done'}
    )

    assert response.status_code == 400
    with app.app_context():
        assert db.session.get(type(task), task.id).status == 'Todo'


def test_mentor_can_follow_multiple_interns(
    app,
    user_factory,
    team_factory
):
    mentor = user_factory(username='multi_mentor')
    first_intern = user_factory(username='first_intern')
    second_intern = user_factory(username='second_intern')
    team = team_factory(
        mentor,
        [(first_intern, 'Intern'), (second_intern, 'Intern')]
    )

    create_internship(team, mentor, first_intern)
    create_internship(team, mentor, second_intern)

    with app.app_context():
        internships = db.session.scalars(
            db.select(Internship).where(
                Internship.mentor_id == mentor.id
            )
        ).all()
        assert {item.intern_id for item in internships} == {
            first_intern.id,
            second_intern.id,
        }


def test_submission_requires_commit_message_and_work_url(
    client,
    app,
    user_factory,
    team_factory,
    task_factory,
    login
):
    mentor = user_factory()
    intern = user_factory()
    team = team_factory(mentor, [(intern, 'Intern')])
    create_internship(team, mentor, intern)
    task = task_factory(team, mentor, assignee=intern)
    login(intern)

    response = client.post(
        f'/tasks/{task.id}/submissions',
        data={
            'summary': 'Çalışmayı tamamladım.',
            'commit_message': '',
            'work_url': '',
        },
        follow_redirects=True
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'Commit mesajı gereklidir' in body
    assert 'GitHub commit veya pull request bağlantısı gereklidir' in body
    with app.app_context():
        assert db.session.scalar(db.select(TaskSubmission)) is None
