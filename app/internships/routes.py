from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from app.internships import internships_bp
from app.models import DailyLog, Internship, Task, TeamMember, User
from app.models.base import utc_now
from extensions import db


INTERNSHIP_STATUSES = {'Planned', 'Active', 'Completed', 'Cancelled'}
DAILY_LOG_REVIEW_STATUSES = {'Approved', 'Revision Requested'}


def get_visible_internship(internship_id):
    internship = db.session.get(Internship, internship_id)
    if internship is None:
        abort(404)

    if current_user.id not in {
        internship.mentor_id,
        internship.intern_id
    }:
        abort(404)

    # Staj kaydındaki rol tek başına yetmez; kullanıcı ilgili ekipten
    # çıkarıldıysa staj kaydına erişimi de sona erer.
    membership = db.session.scalar(
        db.select(TeamMember).where(
            TeamMember.team_id == internship.team_id,
            TeamMember.user_id == current_user.id
        )
    )
    if membership is None:
        abort(404)

    return internship


def get_mentor_internship(internship_id):
    internship = get_visible_internship(internship_id)
    if internship.mentor_id != current_user.id:
        abort(403)
    return internship


def get_intern_log(log_id):
    daily_log = db.session.get(DailyLog, log_id)
    if daily_log is None:
        abort(404)

    internship = get_visible_internship(daily_log.internship_id)
    if internship.intern_id != current_user.id:
        abort(403)

    return internship, daily_log


@internships_bp.route('/')
@login_required
def index():
    internships = db.session.scalars(
        db.select(Internship)
        .where(
            or_(
                Internship.mentor_id == current_user.id,
                Internship.intern_id == current_user.id
            )
        )
        .order_by(Internship.start_date.desc())
    ).all()

    mentor_team_count = 0
    if current_user.is_personnel:
        mentor_team_count = db.session.scalar(
            db.select(db.func.count(TeamMember.id)).where(
                TeamMember.user_id == current_user.id,
                TeamMember.role.in_(['Admin', 'Member'])
            )
        )

    return render_template(
        'internships/index.html',
        internships=internships,
        can_create=bool(mentor_team_count)
    )


@internships_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if not current_user.is_personnel:
        abort(403)

    mentor_memberships = db.session.scalars(
        db.select(TeamMember).where(
            TeamMember.user_id == current_user.id,
            TeamMember.role.in_(['Admin', 'Member'])
        )
    ).all()

    if not mentor_memberships:
        abort(403)

    intern_users = db.session.scalars(
        db.select(User)
        .where(User.account_type == 'Intern')
        .order_by(User.username.asc())
    ).all()

    errors = []
    values = {
        'team_id': '',
        'intern_id': '',
        'company_unit': '',
        'internship_role': '',
        'start_date': '',
        'end_date': '',
    }

    if request.method == 'POST':
        values = {
            key: request.form.get(key, '').strip()
            for key in values
        }

        try:
            team_id = int(values['team_id'])
            intern_id = int(values['intern_id'])
        except ValueError:
            errors.append('Geçerli bir ekip ve stajyer seçin.')
            team_id = None
            intern_id = None

        mentor_membership = None
        intern_user = None
        if team_id is not None:
            mentor_membership = db.session.scalar(
                db.select(TeamMember).where(
                    TeamMember.team_id == team_id,
                    TeamMember.user_id == current_user.id,
                    TeamMember.role.in_(['Admin', 'Member'])
                )
            )
        if intern_id is not None:
            intern_user = db.session.scalar(
                db.select(User).where(
                    User.id == intern_id,
                    User.account_type == 'Intern'
                )
            )

        if mentor_membership is None:
            errors.append(
                'Staj programı yalnızca üyesi olduğunuz bir ekip için oluşturulabilir.'
            )
        if intern_user is None:
            errors.append('Geçerli bir stajyer hesabı seçin.')

        if not values['company_unit'] or len(values['company_unit']) > 150:
            errors.append(
                'Çalışılan birim gereklidir ve en fazla 150 karakter olabilir.'
            )
        if (
            not values['internship_role']
            or len(values['internship_role']) > 150
        ):
            errors.append(
                'Staj rolü gereklidir ve en fazla 150 karakter olabilir.'
            )

        try:
            start_date = datetime.strptime(
                values['start_date'],
                '%Y-%m-%d'
            ).date()
            end_date = datetime.strptime(
                values['end_date'],
                '%Y-%m-%d'
            ).date()
            if start_date > end_date:
                errors.append('Staj başlangıç tarihi bitiş tarihinden sonra olamaz.')
        except ValueError:
            start_date = None
            end_date = None
            errors.append('Geçerli başlangıç ve bitiş tarihleri girin.')

        if team_id is not None and intern_id is not None:
            existing = db.session.scalar(
                db.select(Internship).where(
                    Internship.intern_id == intern_id,
                    Internship.status.in_(['Planned', 'Active'])
                )
            )
            if existing:
                errors.append(
                    'Bu stajyerin devam eden bir staj kaydı zaten var. '
                    'Yeni kayıt için mevcut stajın tamamlanması gerekir.'
                )

        if not errors:
            intern_membership = db.session.scalar(
                db.select(TeamMember).where(
                    TeamMember.team_id == team_id,
                    TeamMember.user_id == intern_id
                )
            )

            if intern_membership is None:
                db.session.add(
                    TeamMember(
                        team_id=team_id,
                        user_id=intern_id,
                        role='Intern'
                    )
                )

            status = 'Active' if start_date <= date.today() else 'Planned'
            internship = Internship(
                team_id=team_id,
                intern_id=intern_id,
                mentor_id=current_user.id,
                company_unit=values['company_unit'],
                internship_role=values['internship_role'],
                start_date=start_date,
                end_date=end_date,
                status=status
            )
            db.session.add(internship)
            db.session.commit()
            flash('Staj programı başarıyla oluşturuldu.', 'success')
            return redirect(
                url_for('internships.detail', internship_id=internship.id)
            )

    return render_template(
        'internships/create.html',
        mentor_memberships=mentor_memberships,
        intern_users=intern_users,
        errors=errors,
        values=values
    )


@internships_bp.route('/<int:internship_id>')
@login_required
def detail(internship_id):
    internship = get_visible_internship(internship_id)
    tasks = db.session.scalars(
        db.select(Task)
        .where(
            Task.team_id == internship.team_id,
            Task.assigned_to_id == internship.intern_id
        )
        .order_by(Task.created_at.desc())
    ).all()
    daily_logs = db.session.scalars(
        db.select(DailyLog)
        .where(DailyLog.internship_id == internship.id)
        .order_by(DailyLog.work_date.desc())
    ).all()

    completed_tasks = sum(task.status == 'Done' for task in tasks)
    progress = round(completed_tasks / len(tasks) * 100) if tasks else 0

    return render_template(
        'internships/detail.html',
        internship=internship,
        tasks=tasks,
        daily_logs=daily_logs,
        completed_tasks=completed_tasks,
        progress=progress,
        today=date.today()
    )


@internships_bp.route('/<int:internship_id>/status', methods=['POST'])
@login_required
def update_status(internship_id):
    internship = get_mentor_internship(internship_id)
    status = request.form.get('status', '')
    if status not in INTERNSHIP_STATUSES:
        abort(400)

    internship.status = status
    db.session.commit()
    flash('Staj programının durumu güncellendi.', 'success')
    return redirect(
        url_for('internships.detail', internship_id=internship.id)
    )


@internships_bp.route(
    '/<int:internship_id>/daily-logs/new',
    methods=['GET', 'POST']
)
@login_required
def create_daily_log(internship_id):
    internship = get_visible_internship(internship_id)
    if internship.intern_id != current_user.id:
        abort(403)

    daily_log = DailyLog(
        internship_id=internship.id,
        work_date=date.today(),
        title='',
        work_summary='',
        learned='',
        blockers='',
        hours=Decimal('8.0')
    )
    return save_daily_log_form(internship, daily_log, is_new=True)


@internships_bp.route('/daily-logs/<int:log_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_daily_log(log_id):
    internship, daily_log = get_intern_log(log_id)
    if daily_log.status == 'Approved':
        abort(403)
    return save_daily_log_form(internship, daily_log, is_new=False)


def save_daily_log_form(internship, daily_log, is_new):
    errors = []

    if request.method == 'POST':
        work_date_value = request.form.get('work_date', '')
        daily_log.title = request.form.get('title', '').strip()
        daily_log.work_summary = request.form.get('work_summary', '').strip()
        daily_log.learned = request.form.get('learned', '').strip()
        daily_log.blockers = request.form.get('blockers', '').strip()
        hours_value = request.form.get('hours', '').strip()

        try:
            work_date = datetime.strptime(work_date_value, '%Y-%m-%d').date()
            if not internship.start_date <= work_date <= internship.end_date:
                errors.append('Çalışma tarihi staj tarihleri arasında olmalıdır.')
            daily_log.work_date = work_date
        except ValueError:
            errors.append('Geçerli bir çalışma tarihi girin.')

        if not daily_log.title or len(daily_log.title) > 150:
            errors.append('Başlık gereklidir ve en fazla 150 karakter olabilir.')
        if not daily_log.work_summary:
            errors.append('Günlük çalışma özeti gereklidir.')

        try:
            hours = Decimal(hours_value)
            if hours <= 0 or hours > 24:
                raise InvalidOperation
            daily_log.hours = hours
        except (InvalidOperation, ValueError):
            errors.append('Çalışma saati 0 ile 24 arasında olmalıdır.')

        duplicate = db.session.scalar(
            db.select(DailyLog).where(
                DailyLog.internship_id == internship.id,
                DailyLog.work_date == daily_log.work_date,
                DailyLog.id != daily_log.id
            )
        )
        if duplicate:
            errors.append('Bu tarih için daha önce günlük kayıt oluşturdunuz.')

        if not errors:
            daily_log.status = 'Submitted'
            daily_log.mentor_feedback = None
            daily_log.reviewed_at = None
            if is_new:
                db.session.add(daily_log)
            db.session.commit()
            flash('Günlük çalışma kaydınız mentöre gönderildi.', 'success')
            return redirect(
                url_for('internships.detail', internship_id=internship.id)
            )

    return render_template(
        'internships/daily_log_form.html',
        internship=internship,
        daily_log=daily_log,
        errors=errors,
        is_new=is_new
    )


@internships_bp.route('/daily-logs/<int:log_id>/review', methods=['POST'])
@login_required
def review_daily_log(log_id):
    daily_log = db.session.get(DailyLog, log_id)
    if daily_log is None:
        abort(404)

    internship = get_mentor_internship(daily_log.internship_id)
    status = request.form.get('status', '')
    feedback = request.form.get('mentor_feedback', '').strip()

    if status not in DAILY_LOG_REVIEW_STATUSES:
        abort(400)
    if status == 'Revision Requested' and not feedback:
        flash('Düzeltme isterken açıklama yazmalısınız.', 'warning')
        return redirect(
            url_for('internships.detail', internship_id=internship.id)
        )
    if len(feedback) > 2000:
        abort(400)

    daily_log.status = status
    daily_log.mentor_feedback = feedback or None
    daily_log.reviewed_at = utc_now()
    db.session.commit()

    message = (
        'Günlük kayıt onaylandı.'
        if status == 'Approved'
        else 'Günlük kayıt için düzeltme istendi.'
    )
    flash(message, 'success')
    return redirect(
        url_for('internships.detail', internship_id=internship.id)
    )
