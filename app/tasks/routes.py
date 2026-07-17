from flask import abort , flash , redirect , render_template, request, url_for
from flask_login import login_required , current_user
from datetime import datetime, timedelta
from app.models import Activity, Comment, Task, TeamMember, User
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
        .where(TeamMember.team_id.in_(team_ids))
        .distinct()
        .order_by(User.username.asc())
    ).all()

    query = db.select(Task).where(
        Task.team_id.in_(team_ids)
    )

    if search:
        query = query.where(
            Task.title.ilike(f'%{search}%')
        )

    allowed_statuses = [
        'Todo',
        'In Progress',
        'Done'
    ]

    if selected_status in allowed_statuses:
        query = query.where(
            Task.status == selected_status
        )
    else:
        selected_status = ''

    allowed_priorities = [
        'Low',
        'Medium',
        'High'
    ]

    if selected_priority in allowed_priorities:
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

    team = current_membership.team

    members = []

    if current_membership.role == 'Admin':
        members = db.session.scalars(
            db.select(TeamMember).where(
                TeamMember.team_id == team_id
            )
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

        allowed_priorities = ['Low', 'Medium', 'High']

        if priority not in allowed_priorities:
            errors.append('Geçersiz görev önceliği.')

        assigned_to_id = None

        if current_membership.role != 'Admin':
            if assigned_to_value:
                errors.append(
                    'Görev atama yetkisi yalnızca Admin kullanıcılara aittir.'
                )

            assigned_to_value = ''

        else:
            if assigned_to_value:
                try:
                    assigned_to_id = int(assigned_to_value)
                except ValueError:
                    errors.append('Geçersiz kullanıcı seçimi.')

            if assigned_to_id is not None:
                assigned_membership = db.session.scalar(
                    db.select(TeamMember).where(
                        TeamMember.team_id == team_id,
                        TeamMember.user_id == assigned_to_id
                    )
                )

                if assigned_membership is None:
                    errors.append(
                        'Görev yalnızca ekip üyelerinden birine atanabilir.'
                    )

        due_date = None

        if due_date_value:
            try:
                due_date = datetime.strptime(
                    due_date_value,
                    '%Y-%m-%d'
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
        due_date_value=due_date_value
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

    members = []

    if current_membership.role == 'Admin':
        members = db.session.scalars(
            db.select(TeamMember).where(
                TeamMember.team_id == task.team_id
            )
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

    return render_template(
        'tasks/detail.html',
        task=task,
        current_membership=current_membership,
        members=members,
        comments=comments,
        activities=activities
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

    is_admin = current_membership.role == 'Admin'
    is_assignee = task.assigned_to_id == current_user.id

    if not is_admin and not is_assignee:
        abort(403)

    new_status = request.form.get('status', '')

    allowed_statuses = [
        'Todo',
        'In Progress',
        'Done'
    ]

    if new_status not in allowed_statuses:
        abort(400)

    old_status = task.status
    task.status = new_status

    if old_status != new_status:
        record_activity(
            task,
            f'Durum {old_status} değerinden {new_status} değerine değiştirildi.'
        )

    db.session.commit()

    flash(
        f'{task.title} görevinin durumu '
        f'{new_status} olarak değiştirildi.',
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

    if current_membership.role != 'Admin':
        abort(403)

    priority = request.form.get('priority', '')
    assigned_to_value = request.form.get('assigned_to_id', '')

    allowed_priorities = [
        'Low',
        'Medium',
        'High'
    ]

    if priority not in allowed_priorities:
        abort(400)

    assigned_to_id = None

    if assigned_to_value:
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
            f'Öncelik {old_priority} değerinden {priority} değerine değiştirildi.'
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

        if due_date_value:
            try:
                due_date = datetime.strptime(
                    due_date_value,
                    '%Y-%m-%d'
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

    if current_membership.role != 'Admin':
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
