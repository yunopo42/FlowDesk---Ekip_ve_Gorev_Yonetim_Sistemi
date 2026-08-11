from flask import abort , flash , redirect , render_template, request, url_for
from flask_login import login_required , current_user
from datetime import datetime, time, timedelta
from urllib.parse import urlparse

from app.models import (
    Activity,
    Comment,
    Internship,
    Task,
    TASK_PRIORITIES,
    TASK_PRIORITY_LABELS,
    TASK_STATUS_LABELS,
    TASK_STATUSES,
    TaskSubmission,
    TeamMember,
    User,
)
from app.models.base import utc_now
from app.tasks import tasks_bp
from extensions import db


def record_activity(task, action):
    """Görevde yapılan bir işlemi, işlemi yapan kullanıcıyla kaydeder."""
    activity = Activity(
        action=action,
        task=task,
        user_id=current_user.id
    )

    db.session.add(activity)


def get_active_internship(task):
    """Göreve atanmış stajyerin bu ekipteki güncel staj kaydını döndürür."""
    if task.assigned_to_id is None:
        return None

    return db.session.scalar(
        db.select(Internship).where(
            Internship.team_id == task.team_id,
            Internship.intern_id == task.assigned_to_id,
            Internship.status.in_(['Planned', 'Active'])
        )
    )


def can_review_intern_submission(task, membership, internship=None):
    """Teslimi staj mentörü, görevi veren personel veya ekip yöneticisi inceler."""
    if not current_user.is_personnel:
        return False

    # Görevi oluşturan yazılım personeli, verdiği işin doğal değerlendiricisidir.
    if task.created_by_id == current_user.id:
        return True

    internship = internship or get_active_internship(task)
    if internship is not None and internship.mentor_id == current_user.id:
        return True

    # Ekip yöneticisi, görev sahibinin erişilemediği durumlarda süreci yönetebilir.
    return membership.role == 'Admin'


@tasks_bp.route('/')
@login_required
def index():
    search = request.args.get('q', '').strip()
    selected_status = request.args.get('status', '').strip()
    selected_priority = request.args.get(
        'priority',
        ''
    ).strip()
    selected_assignee = request.args.get(
        'assignee',
        ''
    ).strip()
    due_from_value = request.args.get(
        'due_from',
        ''
    ).strip()
    due_to_value = request.args.get(
        'due_to',
        ''
    ).strip()

    team_ids = db.select(TeamMember.team_id).where(
        TeamMember.user_id == current_user.id
    )

    available_assignees = db.session.scalars(
        db.select(User)
        .join(TeamMember)
        .where(
            TeamMember.team_id.in_(team_ids)
        )
        .distinct()
        .order_by(User.username.asc())
    ).all()

    query = db.select(Task).where(
        Task.team_id.in_(team_ids)
    )

    if current_user.is_intern:
        query = query.where(Task.assigned_to_id == current_user.id)

    if search:
        query = query.where(
            Task.title.ilike(f'%{search}%')
        )

    if selected_status in TASK_STATUSES:
        query = query.where(
            Task.status == selected_status
        )
    else:
        selected_status = ''

    if selected_priority in TASK_PRIORITIES:
        query = query.where(
            Task.priority == selected_priority
        )
    else:
        selected_priority = ''

    selected_assignee_id = None

    if selected_assignee:
        try:
            candidate_assignee_id = int(selected_assignee)
        except ValueError:
            selected_assignee = ''
        else:
            available_assignee_ids = {
                user.id for user in available_assignees
            }

            if candidate_assignee_id in available_assignee_ids:
                selected_assignee_id = candidate_assignee_id

                query = query.where(
                    Task.assigned_to_id == selected_assignee_id
                )
            else:
                selected_assignee = ''

    due_from = None
    due_to = None
    date_filter_error = ''

    if due_from_value:
        try:
            due_from = datetime.strptime(
                due_from_value,
                '%Y-%m-%d'
            )
        except ValueError:
            date_filter_error = 'Geçersiz başlangıç tarihi.'

    if due_to_value:
        try:
            due_to = datetime.strptime(
                due_to_value,
                '%Y-%m-%d'
            )
        except ValueError:
            date_filter_error = 'Geçersiz bitiş tarihi.'

    if not date_filter_error:
        if due_from and due_to and due_from > due_to:
            date_filter_error = (
                'Başlangıç tarihi bitiş tarihinden '
                'sonra olamaz.'
            )
        else:
            if due_from:
                query = query.where(
                    Task.due_date >= due_from
                )

            if due_to:
                query = query.where(
                    Task.due_date < due_to + timedelta(days=1)
                )

    tasks = db.session.scalars(
        query.order_by(Task.created_at.desc())
    ).all()

    return render_template(
        'tasks/index.html',
        tasks=tasks,
        search=search,
        selected_status=selected_status,
        selected_priority=selected_priority,
        selected_assignee_id=selected_assignee_id,
        available_assignees=available_assignees,
        due_from_value=due_from_value,
        due_to_value=due_to_value,
        date_filter_error=date_filter_error
        )

@tasks_bp.route(
    '/create/<int:team_id>',
    methods=['GET', 'POST']
)
@login_required
def create(team_id):
    current_membership = db.session.scalar(
        db.select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == current_user.id
        )
    )

    if current_membership is None:
        abort(404)

    if (
        not current_user.is_personnel
        or current_membership.role not in ['Admin', 'Member']
    ):
        abort(403)

    team = current_membership.team

    members = db.session.scalars(
        db.select(TeamMember).where(TeamMember.team_id == team_id)
        .order_by(TeamMember.role.asc(), TeamMember.id.asc())
    ).all()

    errors = []
    title = ''
    description = ''
    priority = 'Medium'
    assigned_to_value = ''
    due_date_value = ''

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        priority = request.form.get('priority', 'Medium')
        assigned_to_value = request.form.get(
            'assigned_to_id',
            ''
        )
        due_date_value = request.form.get('due_date', '')

        if not title:
            errors.append('Görev başlığı gereklidir.')
        elif len(title) < 3:
            errors.append(
                'Görev başlığı en az 3 karakter olmalıdır.'
            )
        elif len(title) > 150:
            errors.append(
                'Görev başlığı en fazla 150 karakter olabilir.'
            )

        if priority not in TASK_PRIORITIES:
            errors.append('Geçersiz görev önceliği.')

        assigned_to_id = None

        if not assigned_to_value:
            errors.append('Görevin atanacağı ekip üyesini seçin.')
        else:
            try:
                assigned_to_id = int(assigned_to_value)
            except ValueError:
                errors.append('Geçersiz ekip üyesi seçimi.')

        if assigned_to_id is not None:
            assigned_membership = db.session.scalar(
                db.select(TeamMember).where(
                    TeamMember.team_id == team_id,
                    TeamMember.user_id == assigned_to_id
                )
            )

            if assigned_membership is None:
                errors.append('Görev yalnızca ekipteki bir kullanıcıya atanabilir.')

        due_date = None

        if not due_date_value:
            errors.append('Son teslim tarihi gereklidir.')
        else:
            try:
                parsed_due_date = datetime.strptime(
                    due_date_value,
                    '%Y-%m-%d'
                ).date()
                due_date = datetime.combine(parsed_due_date, time.max)
                if parsed_due_date < datetime.now().date():
                    errors.append(
                        'Son teslim tarihi geçmiş bir tarih olamaz.'
                    )
            except ValueError:
                errors.append('Geçersiz son teslim tarihi.')

        if not errors:
            task = Task(
                title=title,
                description=description,
                priority=priority,
                status='Todo',
                due_date=due_date,
                team_id=team_id,
                created_by_id=current_user.id,
                assigned_to_id=assigned_to_id
            )

            db.session.add(task)
            record_activity(task, 'Görev oluşturuldu.')
            db.session.commit()

            flash(
                f'{task.title} görevi başarıyla oluşturuldu.',
                'success'
            )

            return redirect(url_for('tasks.index'))

    return render_template(
        'tasks/create.html',
        team=team,
        members=members,
        current_membership=current_membership,
        errors=errors,
        title=title,
        description=description,
        priority=priority,
        assigned_to_value=assigned_to_value,
        due_date_value=due_date_value,
        today=datetime.now().date().isoformat()
    )

@tasks_bp.route('/<int:task_id>')
@login_required
def detail(task_id):
    task = db.session.get(Task, task_id)

    if task is None:
        abort(404)

    current_membership = db.session.scalar(
        db.select(TeamMember).where(
            TeamMember.team_id == task.team_id,
            TeamMember.user_id == current_user.id
        )
    )

    if current_membership is None:
        abort(404)

    if current_user.is_intern and task.assigned_to_id != current_user.id:
        abort(404)

    members = []

    if (
        current_user.is_personnel
        and (
            current_membership.role == 'Admin'
            or task.created_by_id == current_user.id
        )
    ):
        members = db.session.scalars(
            db.select(TeamMember)
            .where(TeamMember.team_id == task.team_id)
            .order_by(TeamMember.role.asc(), TeamMember.id.asc())
        ).all()

    comments = db.session.scalars(
        db.select(Comment)
        .where(Comment.task_id == task.id)
        .order_by(Comment.created_at.asc())
    ).all()

    activities = db.session.scalars(
        db.select(Activity)
        .where(Activity.task_id == task.id)
        .order_by(Activity.created_at.desc())
    ).all()

    internship = get_active_internship(task)
    can_review_submission = can_review_intern_submission(
        task,
        current_membership,
        internship
    )

    return render_template(
        'tasks/detail.html',
        task=task,
        current_membership=current_membership,
        members=members,
        comments=comments,
        activities=activities,
        internship=internship,
        is_intern_task=bool(task.assignee and task.assignee.is_intern),
        can_review_submission=can_review_submission
    )


@tasks_bp.route(
    '/<int:task_id>/status',
    methods=['POST']
)
@login_required
def update_status(task_id):
    task = db.session.get(Task, task_id)

    if task is None:
        abort(404)

    current_membership = db.session.scalar(
        db.select(TeamMember).where(
            TeamMember.team_id == task.team_id,
            TeamMember.user_id == current_user.id
        )
    )

    if current_membership is None:
        abort(404)

    is_personnel_manager = (
        current_user.is_personnel
        and (
            current_membership.role == 'Admin'
            or task.created_by_id == current_user.id
        )
    )
    is_assignee = task.assigned_to_id == current_user.id

    if not is_personnel_manager and not is_assignee:
        abort(403)

    is_intern_task = bool(task.assignee and task.assignee.is_intern)
    pending_submission = db.session.scalar(
        db.select(TaskSubmission).where(
            TaskSubmission.task_id == task.id,
            TaskSubmission.status == 'Pending Review'
        )
    )

    if is_intern_task and pending_submission:
        flash(
            'Bu görev mentör incelemesinde. Durum, mentörün teslimi '
            'onaylaması veya düzeltme istemesiyle değişecektir.',
            'warning'
        )

        return redirect(
            url_for('tasks.detail', task_id=task.id)
        )

    new_status = request.form.get('status', '')

    if is_intern_task:
        # Staj görevleri yalnızca teslim onaylandığında tamamlanır.
        allowed_statuses = ['Todo', 'In Progress']
    elif is_personnel_manager:
        allowed_statuses = TASK_STATUSES
    else:
        allowed_statuses = ['Todo', 'In Progress', 'Done']

    if new_status not in allowed_statuses:
        abort(400)

    old_status = task.status
    task.status = new_status

    if old_status != new_status:
        record_activity(
            task,
            'Durum '
            f'{TASK_STATUS_LABELS.get(old_status, old_status)} değerinden '
            f'{TASK_STATUS_LABELS.get(new_status, new_status)} değerine '
            'değiştirildi.'
        )

    db.session.commit()

    flash(
        f'{task.title} görevinin durumu '
        f'{TASK_STATUS_LABELS.get(new_status, new_status)} olarak '
        'değiştirildi.',
        'success'
    )

    return redirect(
        url_for('tasks.detail', task_id=task.id)
    )



@tasks_bp.route(
    '/<int:task_id>/manage',
    methods=['POST']
)
@login_required
def manage(task_id):
    task = db.session.get(Task, task_id)

    if task is None:
        abort(404)

    current_membership = db.session.scalar(
        db.select(TeamMember).where(
            TeamMember.team_id == task.team_id,
            TeamMember.user_id == current_user.id
        )
    )

    if current_membership is None:
        abort(404)

    if (
        not current_user.is_personnel
        or (
            current_membership.role != 'Admin'
            and task.created_by_id != current_user.id
        )
    ):
        abort(403)

    priority = request.form.get('priority', '')
    assigned_to_value = request.form.get('assigned_to_id', '')

    if priority not in TASK_PRIORITIES:
        abort(400)

    if not assigned_to_value:
        abort(400)

    try:
        assigned_to_id = int(assigned_to_value)
    except ValueError:
        abort(400)

    assigned_membership = db.session.scalar(
        db.select(TeamMember).where(
            TeamMember.team_id == task.team_id,
            TeamMember.user_id == assigned_to_id
        )
    )

    if assigned_membership is None:
        abort(400)

    old_priority = task.priority
    old_assignee_id = task.assigned_to_id
    old_assignee_name = (
        task.assignee.username if task.assignee else None
    )

    new_assignee_name = None
    if assigned_to_id is not None:
        new_assignee_name = assigned_membership.user.username

    task.priority = priority
    task.assigned_to_id = assigned_to_id

    if old_priority != priority:
        record_activity(
            task,
            'Öncelik '
            f'{TASK_PRIORITY_LABELS.get(old_priority, old_priority)} '
            f'değerinden {TASK_PRIORITY_LABELS.get(priority, priority)} '
            'değerine değiştirildi.'
        )

    if old_assignee_id != assigned_to_id:
        if new_assignee_name:
            action = f'Görev {new_assignee_name} kullanıcısına atandı.'
        elif old_assignee_name:
            action = f'{old_assignee_name} kullanıcısının ataması kaldırıldı.'
        else:
            action = 'Görev ataması kaldırıldı.'

        record_activity(task, action)

    db.session.commit()

    flash(
        f'{task.title} görevinin yönetim bilgileri güncellendi.',
        'success'
    )

    return redirect(
        url_for('tasks.detail', task_id=task.id)
    )


@tasks_bp.route(
    '/<int:task_id>/edit',
    methods=['GET', 'POST']
)
@login_required
def edit(task_id):
    task = db.session.get(Task, task_id)

    if task is None:
        abort(404)

    current_membership = db.session.scalar(
        db.select(TeamMember).where(
            TeamMember.team_id == task.team_id,
            TeamMember.user_id == current_user.id
        )
    )

    if current_membership is None:
        abort(404)

    if not current_user.is_personnel:
        abort(403)

    is_admin = current_membership.role == 'Admin'
    is_creator = task.created_by_id == current_user.id

    if not is_admin and not is_creator:
        abort(403)

    errors = []
    title = task.title
    description = task.description or ''

    if task.due_date:
        due_date_value = task.due_date.strftime('%Y-%m-%d')
    else:
        due_date_value = ''

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        due_date_value = request.form.get('due_date', '')

        if not title:
            errors.append('Görev başlığı gereklidir.')
        elif len(title) < 3:
            errors.append(
                'Görev başlığı en az 3 karakter olmalıdır.'
            )
        elif len(title) > 150:
            errors.append(
                'Görev başlığı en fazla 150 karakter olabilir.'
            )

        due_date = None

        if not due_date_value:
            errors.append('Son teslim tarihi gereklidir.')
        else:
            try:
                parsed_due_date = datetime.strptime(
                    due_date_value,
                    '%Y-%m-%d'
                ).date()
                due_date = datetime.combine(parsed_due_date, time.max)
                if parsed_due_date < datetime.now().date():
                    errors.append(
                        'Son teslim tarihi geçmiş bir tarih olamaz.'
                    )
            except ValueError:
                errors.append('Geçersiz son teslim tarihi.')

        if not errors:
            task.title = title
            task.description = description
            task.due_date = due_date

            record_activity(task, 'Görev bilgileri güncellendi.')

            db.session.commit()

            flash(
                'Görev bilgileri başarıyla güncellendi.',
                'success'
            )

            return redirect(
                url_for('tasks.detail', task_id=task.id)
            )

    return render_template(
        'tasks/edit.html',
        task=task,
        errors=errors,
        title=title,
        description=description,
        due_date_value=due_date_value
    )


@tasks_bp.route(
    '/<int:task_id>/delete',
    methods=['POST']
)
@login_required
def delete(task_id):
    task = db.session.get(Task, task_id)

    if task is None:
        abort(404)

    current_membership = db.session.scalar(
        db.select(TeamMember).where(
            TeamMember.team_id == task.team_id,
            TeamMember.user_id == current_user.id
        )
    )

    if current_membership is None:
        abort(404)

    if current_membership.role != 'Admin' or not current_user.is_personnel:
        abort(403)

    task_title = task.title

    db.session.delete(task)
    db.session.commit()

    flash(
        f'{task_title} görevi silindi.',
        'success'
    )

    return redirect(url_for('tasks.index'))


@tasks_bp.route(
    '/<int:task_id>/comments',
    methods=['POST']
)
@login_required
def add_comment(task_id):
    task = db.session.get(Task, task_id)

    if task is None:
        abort(404)

    current_membership = db.session.scalar(
        db.select(TeamMember).where(
            TeamMember.team_id == task.team_id,
            TeamMember.user_id == current_user.id
        )
    )

    if current_membership is None:
        abort(404)

    if current_user.is_intern and task.assigned_to_id != current_user.id:
        abort(403)

    content = request.form.get('content', '').strip()

    if not content:
        flash('Yorum içeriği boş olamaz.', 'warning')

        return redirect(
            url_for('tasks.detail', task_id=task.id)
        )

    if len(content) > 2000:
        flash(
            'Yorum en fazla 2000 karakter olabilir.',
            'warning'
        )

        return redirect(
            url_for('tasks.detail', task_id=task.id)
        )

    comment = Comment(
        content=content,
        task_id=task.id,
        user_id=current_user.id
    )

    db.session.add(comment)
    record_activity(task, 'Göreve yorum eklendi.')
    db.session.commit()

    flash('Yorumunuz eklendi.', 'success')

    return redirect(
        url_for('tasks.detail', task_id=task.id)
    )


@tasks_bp.route('/<int:task_id>/submissions', methods=['POST'])
@login_required
def submit_for_review(task_id):
    task = db.session.get(Task, task_id)
    if task is None:
        abort(404)

    membership = db.session.scalar(
        db.select(TeamMember).where(
            TeamMember.team_id == task.team_id,
            TeamMember.user_id == current_user.id
        )
    )
    if membership is None:
        abort(404)
    if task.assigned_to_id != current_user.id:
        abort(403)

    if not current_user.is_intern:
        abort(403)

    if task.status not in {'Todo', 'In Progress', 'Revision Requested'}:
        flash(
            'Bu görev mevcut durumundayken yeniden teslim edilemez.',
            'warning'
        )
        return redirect(url_for('tasks.detail', task_id=task.id))

    pending_submission = db.session.scalar(
        db.select(TaskSubmission).where(
            TaskSubmission.task_id == task.id,
            TaskSubmission.status == 'Pending Review'
        )
    )
    if pending_submission:
        flash('Bu görev için zaten inceleme bekleyen bir teslim var.', 'warning')
        return redirect(url_for('tasks.detail', task_id=task.id))

    summary = request.form.get('summary', '').strip()
    commit_message = request.form.get('commit_message', '').strip()
    work_url = request.form.get('work_url', '').strip()
    challenges = request.form.get('challenges', '').strip()
    learned = request.form.get('learned', '').strip()
    errors = []

    if not summary:
        errors.append('Teslim açıklaması gereklidir.')
    elif len(summary) > 5000:
        errors.append('Teslim açıklaması en fazla 5000 karakter olabilir.')

    if not commit_message:
        errors.append('Commit mesajı gereklidir.')
    elif len(commit_message) > 255:
        errors.append('Commit mesajı en fazla 255 karakter olabilir.')

    if not work_url:
        errors.append('GitHub commit veya pull request bağlantısı gereklidir.')
    else:
        parsed_url = urlparse(work_url)
        if (
            parsed_url.scheme not in {'http', 'https'}
            or not parsed_url.netloc
            or len(work_url) > 500
        ):
            errors.append('Geçerli bir HTTP veya HTTPS çalışma bağlantısı girin.')

    if len(challenges) > 3000 or len(learned) > 3000:
        errors.append('Sorunlar ve öğrenilenler alanları en fazla 3000 karakter olabilir.')

    if errors:
        for error in errors:
            flash(error, 'warning')
        return redirect(url_for('tasks.detail', task_id=task.id))

    submission = TaskSubmission(
        task_id=task.id,
        submitted_by_id=current_user.id,
        summary=summary,
        commit_message=commit_message,
        work_url=work_url or None,
        challenges=challenges or None,
        learned=learned or None
    )
    task.status = 'Review Pending'
    db.session.add(submission)
    record_activity(task, 'Görev mentör incelemesine gönderildi.')
    db.session.commit()

    flash('Görev tesliminiz mentöre gönderildi.', 'success')
    return redirect(url_for('tasks.detail', task_id=task.id))


@tasks_bp.route('/submissions/<int:submission_id>/review', methods=['POST'])
@login_required
def review_submission(submission_id):
    submission = db.session.get(TaskSubmission, submission_id)
    if submission is None:
        abort(404)

    task = submission.task
    membership = db.session.scalar(
        db.select(TeamMember).where(
            TeamMember.team_id == task.team_id,
            TeamMember.user_id == current_user.id
        )
    )
    if membership is None:
        abort(404)
    internship = get_active_internship(task)
    if not can_review_intern_submission(task, membership, internship):
        abort(403)
    if submission.status != 'Pending Review':
        abort(400)

    decision = request.form.get('decision', '')
    feedback = request.form.get('mentor_feedback', '').strip()
    if decision not in {'Approved', 'Revision Requested'}:
        abort(400)
    if decision == 'Revision Requested' and not feedback:
        flash('Düzeltme isterken açıklama yazmalısınız.', 'warning')
        return redirect(url_for('tasks.detail', task_id=task.id))
    if len(feedback) > 3000:
        abort(400)

    submission.status = decision
    submission.mentor_feedback = feedback or None
    submission.reviewed_by_id = current_user.id
    submission.reviewed_at = utc_now()

    if decision == 'Approved':
        task.status = 'Done'
        action = 'Görev teslimi mentör tarafından onaylandı.'
        message = 'Görev teslimi onaylandı ve görev tamamlandı.'
    else:
        task.status = 'Revision Requested'
        action = 'Görev teslimi için mentör düzeltme istedi.'
        message = 'Görev stajyere düzeltme için geri gönderildi.'

    record_activity(task, action)
    db.session.commit()
    flash(message, 'success')
    return redirect(url_for('tasks.detail', task_id=task.id))
