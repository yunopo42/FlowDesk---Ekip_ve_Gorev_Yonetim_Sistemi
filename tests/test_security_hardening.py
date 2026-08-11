"""Güvenlik sertleştirme testleri.

Bu dosya, güvenlik incelemesinde tespit edilip giderilen açıkların geri
gelmesini engeller. Her test bir saldırı senaryosunu taklit eder.
"""
from datetime import date, timedelta

import pytest

from app.models import DailyLog, Internship, TaskSubmission, TeamMember
from extensions import db


def make_internship(mentor, intern, team, status='Active'):
    internship = Internship(
        team_id=team.id,
        intern_id=intern.id,
        mentor_id=mentor.id,
        company_unit='Yazılım Geliştirme',
        internship_role='Backend Stajyeri',
        start_date=date.today() - timedelta(days=5),
        end_date=date.today() + timedelta(days=30),
        status=status
    )
    db.session.add(internship)
    db.session.commit()
    return internship


def submit_task_for_review(client, task):
    return client.post(
        f'/tasks/{task.id}/submissions',
        data={
            'summary': 'Görevi tamamladım.',
            'commit_message': 'feat: görevi tamamla',
            'work_url': 'https://github.com/ornek/repo/commit/abc123'
        },
        follow_redirects=True
    )


# ---------------------------------------------------------------------------
# Kaba kuvvet (brute force) koruması
# ---------------------------------------------------------------------------

@pytest.mark.ratelimit
def test_repeated_failed_logins_are_rate_limited(
    client,
    user_factory
):
    user_factory(email='kurban@example.com', password='Password123')

    statuses = []
    for attempt in range(15):
        response = client.post(
            '/auth/login',
            data={
                'email': 'kurban@example.com',
                'password': f'yanlis{attempt}'
            }
        )
        statuses.append(response.status_code)

    assert 429 in statuses, (
        'Parola denemeleri sınırsız; kaba kuvvet saldırısı mümkün.'
    )
    # Sınır 10 deneme olduğu için 11. denemeden itibaren engellenmeli.
    assert statuses.index(429) <= 10


@pytest.mark.ratelimit
def test_successful_login_does_not_consume_rate_limit(
    client,
    user_factory
):
    """Doğru parolayla giren kullanıcı sayaç yüzünden kilitlenmemeli."""
    user_factory(email='duzgun@example.com', password='Password123')

    for _ in range(12):
        response = client.post(
            '/auth/login',
            data={
                'email': 'duzgun@example.com',
                'password': 'Password123'
            }
        )
        assert response.status_code == 302
        client.get('/auth/logout')


@pytest.mark.ratelimit
def test_registration_is_rate_limited(client):
    statuses = []
    for index in range(15):
        response = client.post(
            '/auth/register/intern',
            data={
                'username': f'spam_{index}',
                'email': f'spam_{index}@example.com',
                'password': 'Password123',
                'password_confirm': 'Password123'
            }
        )
        statuses.append(response.status_code)

    assert 429 in statuses, 'Kayıt ucu sınırsız hesap açmaya izin veriyor.'


# ---------------------------------------------------------------------------
# Oturum güvenliği
# ---------------------------------------------------------------------------

def test_password_change_invalidates_other_sessions(
    app,
    client,
    user_factory
):
    """Çalınmış bir oturum, parola değişince geçersiz olmalı."""
    user_factory(email='hedef@example.com', password='Password123')

    attacker = app.test_client()
    attacker.post(
        '/auth/login',
        data={
            'email': 'hedef@example.com',
            'password': 'Password123',
            'remember': 'on'
        }
    )
    assert attacker.get('/').status_code == 200

    owner = app.test_client()
    owner.post(
        '/auth/login',
        data={'email': 'hedef@example.com', 'password': 'Password123'}
    )
    change = owner.post(
        '/auth/profile/password',
        data={
            'current_password': 'Password123',
            'new_password': 'YeniParola456',
            'new_password_confirm': 'YeniParola456'
        }
    )
    assert change.status_code == 302

    # Parolayı değiştiren cihaz oturumda kalır.
    assert owner.get('/').status_code == 200

    # Saldırganın hem oturum hem "beni hatırla" çerezi düşer.
    hijacked = attacker.get('/')
    assert hijacked.status_code == 302
    assert '/auth/login' in hijacked.headers['Location']


def test_password_reset_invalidates_existing_sessions(
    app,
    client,
    user_factory
):
    from app.auth.tokens import generate_password_reset_token

    user = user_factory(email='sifirla@example.com', password='Password123')

    stolen = app.test_client()
    stolen.post(
        '/auth/login',
        data={
            'email': 'sifirla@example.com',
            'password': 'Password123',
            'remember': 'on'
        }
    )
    assert stolen.get('/').status_code == 200

    token = generate_password_reset_token(user)
    reset = client.post(
        f'/auth/reset-password/{token}',
        data={
            'password': 'TamamenYeni789',
            'password_confirm': 'TamamenYeni789'
        }
    )
    assert reset.status_code == 302

    assert stolen.get('/').status_code == 302


def test_forged_session_identity_is_rejected(client, user_factory):
    """Parola imzası olmayan / yanlış olan oturum kimliği kabul edilmemeli."""
    user = user_factory(email='imza@example.com')

    for forged in (str(user.id), f'{user.id}|', f'{user.id}|deadbeefdeadbeef'):
        with client.session_transaction() as session:
            session['_user_id'] = forged
            session['_fresh'] = True

        response = client.get('/')
        assert response.status_code == 302, (
            f'Uydurma oturum kimliği kabul edildi: {forged!r}'
        )


# ---------------------------------------------------------------------------
# Güvenlik başlıkları
# ---------------------------------------------------------------------------

def test_templates_contain_no_inline_javascript():
    """CSP satır içi betiği engeller; şablonlarda kalmamalı.

    Satır içi betik veya onclick/onsubmit gibi olay yakalayıcı eklenirse
    tarayıcı bunu sessizce çalıştırmaz ve arayüz bozulur. Davranışlar
    static/js altındaki harici dosyalara taşınmalıdır.
    """
    import re
    from pathlib import Path

    templates = Path(__file__).resolve().parent.parent / 'app' / 'templates'
    inline_handler = re.compile(
        r'\son(?:click|submit|change|input|load|focus|blur|'
        r'mouseover|error)\s*=',
        re.IGNORECASE
    )
    script_tag = re.compile(r'<script([^>]*)>', re.IGNORECASE)

    problems = []

    for path in templates.rglob('*.html'):
        content = path.read_text(encoding='utf-8')
        relative = path.relative_to(templates)

        for match in inline_handler.finditer(content):
            problems.append(
                f'{relative}: satır içi olay yakalayıcı {match.group().strip()}'
            )

        for match in script_tag.finditer(content):
            attributes = match.group(1)
            is_external = 'src=' in attributes
            is_data_block = 'application/json' in attributes

            if not is_external and not is_data_block:
                problems.append(f'{relative}: satır içi <script> bloğu')

    assert not problems, 'CSP ile uyumsuz şablonlar:\n' + '\n'.join(problems)


def test_rate_limit_page_uses_application_layout(client, monkeypatch):
    """429 yanıtı da uygulamanın hata sayfasıyla gösterilmeli."""
    from werkzeug.exceptions import TooManyRequests

    @client.application.route('/_test/429')
    def raise_rate_limit():
        raise TooManyRequests('Deneme sınırı aşıldı.')

    client.application.config['PROPAGATE_EXCEPTIONS'] = False
    response = client.get('/_test/429')
    body = response.get_data(as_text=True)

    assert response.status_code == 429
    assert 'Bir süre beklemeniz gerekiyor' in body
    assert 'Ana navigasyon' in body


def test_content_security_policy_is_restrictive(client):
    policy = client.get('/auth/login').headers.get('Content-Security-Policy')

    assert policy, 'Content-Security-Policy başlığı yok.'
    assert "default-src 'self'" in policy
    assert "object-src 'none'" in policy
    assert "form-action 'self'" in policy
    assert "base-uri 'self'" in policy
    # Betik çalıştırma inline koda açık olmamalı.
    assert "'unsafe-inline'" not in policy.split('script-src')[1].split(';')[0]
    assert "'unsafe-eval'" not in policy


# ---------------------------------------------------------------------------
# Yetki kalıcılığı: ekipten çıkarılan kullanıcı
# ---------------------------------------------------------------------------

def test_removed_member_loses_internship_access(
    client,
    user_factory,
    team_factory,
    login
):
    mentor = user_factory(account_type='Personnel')
    intern = user_factory(account_type='Intern')
    team = team_factory(mentor, [(intern, 'Intern')])
    internship = make_internship(mentor, intern, team)

    membership = db.session.scalar(
        db.select(TeamMember).where(
            TeamMember.team_id == team.id,
            TeamMember.user_id == intern.id
        )
    )
    db.session.delete(membership)
    db.session.commit()

    login(intern)

    assert client.get(f'/internships/{internship.id}').status_code == 404

    log_response = client.post(
        f'/internships/{internship.id}/daily-logs/new',
        data={
            'work_date': date.today().isoformat(),
            'title': 'Yetkisiz kayıt',
            'work_summary': 'Ekipte olmadığım halde yazdım.',
            'hours': '8'
        }
    )
    assert log_response.status_code == 404
    assert db.session.scalar(db.select(db.func.count(DailyLog.id))) == 0


def test_removing_member_unassigns_their_tasks(
    client,
    user_factory,
    team_factory,
    task_factory,
    login
):
    admin = user_factory(account_type='Personnel')
    member = user_factory(account_type='Personnel')
    team = team_factory(admin, [(member, 'Member')])
    task = task_factory(team, admin, assignee=member)

    membership = db.session.scalar(
        db.select(TeamMember).where(
            TeamMember.team_id == team.id,
            TeamMember.user_id == member.id
        )
    )

    login(admin)
    response = client.post(
        f'/teams/{team.id}/members/{membership.id}/remove',
        follow_redirects=True
    )

    assert response.status_code == 200
    db.session.refresh(task)
    assert task.assigned_to_id is None, (
        'Ekipten çıkarılan kullanıcı göreve atanmış kalıyor.'
    )


def test_removing_intern_cancels_their_internship(
    client,
    user_factory,
    team_factory,
    login
):
    mentor = user_factory(account_type='Personnel')
    intern = user_factory(account_type='Intern')
    team = team_factory(mentor, [(intern, 'Intern')])
    internship = make_internship(mentor, intern, team)

    membership = db.session.scalar(
        db.select(TeamMember).where(
            TeamMember.team_id == team.id,
            TeamMember.user_id == intern.id
        )
    )

    login(mentor)
    client.post(
        f'/teams/{team.id}/members/{membership.id}/remove',
        follow_redirects=True
    )

    db.session.refresh(internship)
    assert internship.status == 'Cancelled'


# ---------------------------------------------------------------------------
# İş akışı bütünlüğü
# ---------------------------------------------------------------------------

def test_intern_cannot_revert_task_under_review(
    client,
    user_factory,
    team_factory,
    task_factory,
    login
):
    """İnceleme bekleyen görev geri çekilirse teslim askıda kalırdı."""
    mentor = user_factory(account_type='Personnel')
    intern = user_factory(account_type='Intern')
    team = team_factory(mentor, [(intern, 'Intern')])
    task = task_factory(team, mentor, assignee=intern)

    login(intern)
    submit_task_for_review(client, task)
    db.session.refresh(task)
    assert task.status == 'Review Pending'

    revert = client.post(
        f'/tasks/{task.id}/status',
        data={'status': 'In Progress'},
        follow_redirects=True
    )

    db.session.refresh(task)
    assert task.status == 'Review Pending', (
        'Stajyer incelemedeki görevi geri çekebiliyor.'
    )
    assert 'mentör incelemesinde' in revert.get_data(as_text=True)


def test_mentor_must_review_submission_instead_of_changing_status(
    client,
    user_factory,
    team_factory,
    task_factory,
    login
):
    mentor = user_factory(account_type='Personnel')
    intern = user_factory(account_type='Intern')
    team = team_factory(mentor, [(intern, 'Intern')])
    task = task_factory(team, mentor, assignee=intern)

    login(intern)
    submit_task_for_review(client, task)

    login(mentor)
    response = client.post(
        f'/tasks/{task.id}/status',
        data={'status': 'Revision Requested'},
        follow_redirects=True
    )

    assert response.status_code == 200
    db.session.refresh(task)
    assert task.status == 'Review Pending'
    assert 'mentörün teslimi' in response.get_data(as_text=True)


def test_intern_can_resubmit_after_revision_request(
    client,
    user_factory,
    team_factory,
    task_factory,
    login
):
    """Düzeltme istendikten sonra stajyer kilitlenmemeli."""
    mentor = user_factory(account_type='Personnel')
    intern = user_factory(account_type='Intern')
    team = team_factory(mentor, [(intern, 'Intern')])
    task = task_factory(team, mentor, assignee=intern)

    login(intern)
    submit_task_for_review(client, task)

    submission = db.session.scalar(db.select(TaskSubmission))
    login(mentor)
    client.post(
        f'/tasks/submissions/{submission.id}/review',
        data={
            'decision': 'Revision Requested',
            'mentor_feedback': 'Testleri de ekleyin.'
        },
        follow_redirects=True
    )

    login(intern)
    submit_task_for_review(client, task)

    db.session.refresh(task)
    assert task.status == 'Review Pending'
    assert db.session.scalar(
        db.select(db.func.count(TaskSubmission.id))
    ) == 2


# ---------------------------------------------------------------------------
# Enjeksiyon ve XSS
# ---------------------------------------------------------------------------

def test_user_content_is_html_escaped(
    client,
    user_factory,
    team_factory,
    task_factory,
    login
):
    admin = user_factory(account_type='Personnel')
    team = team_factory(admin)
    payload = '<script>alert("xss")</script>'
    task = task_factory(team, admin, assignee=admin, title=payload)

    login(admin)
    body = client.get(f'/tasks/{task.id}').get_data(as_text=True)

    assert payload not in body, 'Görev başlığı kaçırılmadan basılıyor (XSS).'
    assert '&lt;script&gt;' in body


def test_comment_content_is_html_escaped(
    client,
    user_factory,
    team_factory,
    task_factory,
    login
):
    admin = user_factory(account_type='Personnel')
    team = team_factory(admin)
    task = task_factory(team, admin, assignee=admin)

    login(admin)
    client.post(
        f'/tasks/{task.id}/comments',
        data={'content': '<img src=x onerror=alert(1)>'},
        follow_redirects=True
    )

    body = client.get(f'/tasks/{task.id}').get_data(as_text=True)
    assert '<img src=x onerror=alert(1)>' not in body
    assert '&lt;img src=x onerror=alert(1)&gt;' in body


def test_search_filter_is_not_sql_injectable(
    client,
    user_factory,
    team_factory,
    task_factory,
    login
):
    admin = user_factory(account_type='Personnel')
    team = team_factory(admin)
    task_factory(team, admin, assignee=admin, title='Normal görev')

    login(admin)
    response = client.get("/tasks/?q=' OR 1=1 --")

    assert response.status_code == 200
    assert 'Normal görev' not in response.get_data(as_text=True)
    # Tablo hâlâ ayakta olmalı.
    assert client.get('/tasks/').status_code == 200


# ---------------------------------------------------------------------------
# Yetkisiz erişim (IDOR) ve yetki yükseltme
# ---------------------------------------------------------------------------

def test_outsider_cannot_reach_another_teams_resources(
    client,
    user_factory,
    team_factory,
    task_factory,
    login
):
    owner = user_factory(account_type='Personnel')
    outsider = user_factory(account_type='Personnel')
    team = team_factory(owner)
    other_team = team_factory(outsider)
    task = task_factory(team, owner, assignee=owner)
    internship_intern = user_factory(account_type='Intern')
    team_factory(owner, [(internship_intern, 'Intern')], name='Staj Ekibi')
    internship = make_internship(owner, internship_intern, team)

    login(outsider)

    assert other_team is not None
    assert client.get(f'/teams/{team.id}').status_code == 404
    assert client.get(f'/tasks/{task.id}').status_code == 404
    assert client.get(f'/tasks/{task.id}/edit').status_code == 404
    assert client.get(f'/internships/{internship.id}').status_code == 404
    assert client.post(
        f'/tasks/{task.id}/delete'
    ).status_code == 404
    assert client.post(
        f'/tasks/{task.id}/status',
        data={'status': 'Done'}
    ).status_code == 404


def test_intern_cannot_be_promoted_to_admin(
    client,
    user_factory,
    team_factory,
    login
):
    admin = user_factory(account_type='Personnel')
    intern = user_factory(account_type='Intern')
    team = team_factory(admin, [(intern, 'Intern')])

    membership = db.session.scalar(
        db.select(TeamMember).where(
            TeamMember.team_id == team.id,
            TeamMember.user_id == intern.id
        )
    )

    login(admin)
    response = client.post(
        f'/teams/{team.id}/members/{membership.id}/role',
        data={'role': 'Admin'}
    )

    assert response.status_code == 400
    db.session.refresh(membership)
    assert membership.role == 'Intern'


def test_intern_cannot_escalate_via_task_management(
    client,
    user_factory,
    team_factory,
    task_factory,
    login
):
    admin = user_factory(account_type='Personnel')
    intern = user_factory(account_type='Intern')
    team = team_factory(admin, [(intern, 'Intern')])
    task = task_factory(team, admin, assignee=intern)

    login(intern)

    assert client.post(
        f'/tasks/{task.id}/manage',
        data={'priority': 'High', 'assigned_to_id': intern.id}
    ).status_code == 403
    assert client.post(f'/tasks/{task.id}/delete').status_code == 403
    assert client.get(f'/tasks/{task.id}/edit').status_code == 403
    assert client.get(f'/tasks/create/{team.id}').status_code == 403


def test_login_does_not_follow_attacker_supplied_next(client, user_factory):
    """Açık yönlendirme (open redirect) olmamalı."""
    user_factory(email='yonlendir@example.com', password='Password123')

    response = client.post(
        '/auth/login?next=https://kotu-site.example.com/',
        data={
            'email': 'yonlendir@example.com',
            'password': 'Password123'
        }
    )

    assert response.status_code == 302
    assert 'kotu-site' not in response.headers['Location']


def test_profile_photo_rejects_non_image_upload(
    client,
    user_factory,
    login
):
    """Dosya adı .png olsa bile içerik doğrulanmalı."""
    import io

    user = user_factory(email='yukleme@example.com')
    login(user)

    response = client.post(
        '/auth/profile/update',
        data={
            'username': user.username,
            'email': user.email,
            'phone': '',
            'profile_image': (
                io.BytesIO(b'<?php system($_GET["c"]); ?>'),
                'shell.png'
            )
        },
        content_type='multipart/form-data'
    )

    assert response.status_code == 400
    db.session.refresh(user)
    assert user.profile_image is None
