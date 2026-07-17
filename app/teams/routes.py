from flask import abort ,flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.models import Team, TeamMember , User
from app.teams import teams_bp
from extensions import db


@teams_bp.route('/')
@login_required
def index():
    memberships = db.session.scalars(
        db.select(TeamMember).where(
            TeamMember.user_id == current_user.id
        )
    ).all()

    return render_template(
        'teams/index.html',
        memberships=memberships
    )

@teams_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    errors = []
    name = ''
    description = ''

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()

        if not name:
            errors.append('Ekip adı gereklidir.')
        elif len(name) < 3:
            errors.append('Ekip adı en az 3 karakter olmalıdır.')
        elif len(name) > 100:
            errors.append('Ekip adı en fazla 100 karakter olabilir.')

        if len(description) > 255:
            errors.append(
                'Ekip açıklaması en fazla 255 karakter olabilir.'
            )

        if not errors:
            team = Team(
                name=name,
                description=description
            )

            membership = TeamMember(
                team=team,
                user_id=current_user.id,
                role='Admin'
            )

            db.session.add_all([team, membership])
            db.session.commit()

            flash(
                f'{team.name} ekibi başarıyla oluşturuldu.',
                'success'
            )

            return redirect(url_for('teams.index'))

    return render_template(
        'teams/create.html',
        errors=errors,
        name=name,
        description=description
    )
@teams_bp.route('/<int:team_id>')
@login_required
def detail(team_id):
    membership = db.session.scalar(
        db.select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == current_user.id
        )
    )

    if membership is None:
        abort(404)

    return render_template(
        'teams/detail.html',
        team=membership.team,
        current_membership=membership
    )

@teams_bp.route(
    '/<int:team_id>/members/add',
    methods=['GET', 'POST']
)
@login_required
def add_member(team_id):
    current_membership = db.session.scalar(
        db.select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == current_user.id
        )
    )

    if current_membership is None:
        abort(404)

    if current_membership.role != 'Admin':
        abort(403)

    errors = []
    email = ''

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()

        if not email:
            errors.append('E-posta adresi gereklidir.')
        elif '@' not in email:
            errors.append('Geçerli bir e-posta adresi girin.')

        user = None

        if not errors:
            user = db.session.scalar(
                db.select(User).where(User.email == email)
            )

            if user is None:
                errors.append(
                    'Bu e-posta adresiyle kayıtlı kullanıcı bulunamadı.'
                )

        if not errors:
            existing_membership = db.session.scalar(
                db.select(TeamMember).where(
                    TeamMember.team_id == team_id,
                    TeamMember.user_id == user.id
                )
            )

            if existing_membership:
                errors.append('Bu kullanıcı zaten ekibin üyesi.')

        if not errors:
            membership = TeamMember(
                team_id=team_id,
                user_id=user.id,
                role='Member'
            )

            db.session.add(membership)
            db.session.commit()

            flash(
                f'{user.username} ekibe başarıyla eklendi.',
                'success'
            )

            return redirect(
                url_for('teams.detail', team_id=team_id)
            )

    return render_template(
        'teams/add_member.html',
        team=current_membership.team,
        errors=errors,
        email=email
    )

@teams_bp.route(
    '/<int:team_id>/members/<int:membership_id>/role',
    methods=['POST']
)
@login_required
def update_member_role(team_id, membership_id):
    current_membership = db.session.scalar(
        db.select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == current_user.id
        )
    )

    if current_membership is None:
        abort(404)

    if current_membership.role != 'Admin':
        abort(403)

    target_membership = db.session.scalar(
        db.select(TeamMember).where(
            TeamMember.id == membership_id,
            TeamMember.team_id == team_id
        )
    )

    if target_membership is None:
        abort(404)

    new_role = request.form.get('role', '')

    if new_role not in ['Admin', 'Member']:
        abort(400)

    if (
        target_membership.user_id == current_user.id
        and new_role != 'Admin'
    ):
        flash(
            'Kendi Admin rolünüzü değiştiremezsiniz.',
            'warning'
        )

        return redirect(
            url_for('teams.detail', team_id=team_id)
        )

    if (
        target_membership.role == 'Admin'
        and new_role == 'Member'
    ):
        admin_count = db.session.scalar(
            db.select(db.func.count())
            .select_from(TeamMember)
            .where(
                TeamMember.team_id == team_id,
                TeamMember.role == 'Admin'
            )
        )

        if admin_count <= 1:
            flash(
                'Ekipte en az bir Admin bulunmalıdır.',
                'warning'
            )

            return redirect(
                url_for('teams.detail', team_id=team_id)
            )

    target_membership.role = new_role
    db.session.commit()

    flash(
        f'{target_membership.user.username} kullanıcısının '
        f'rolü {new_role} olarak değiştirildi.',
        'success'
    )

    return redirect(
        url_for('teams.detail', team_id=team_id)
    )

@teams_bp.route(
    '/<int:team_id>/members/<int:membership_id>/remove',
    methods=['POST']
)
@login_required
def remove_member(team_id, membership_id):
    current_membership = db.session.scalar(
        db.select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == current_user.id
        )
    )

    if current_membership is None:
        abort(404)

    if current_membership.role != 'Admin':
        abort(403)

    target_membership = db.session.scalar(
        db.select(TeamMember).where(
            TeamMember.id == membership_id,
            TeamMember.team_id == team_id
        )
    )

    if target_membership is None:
        abort(404)

    if target_membership.user_id == current_user.id:
        flash(
            'Kendinizi ekipten çıkaramazsınız.',
            'warning'
        )

        return redirect(
            url_for('teams.detail', team_id=team_id)
        )

    if target_membership.role == 'Admin':
        admin_count = db.session.scalar(
            db.select(db.func.count())
            .select_from(TeamMember)
            .where(
                TeamMember.team_id == team_id,
                TeamMember.role == 'Admin'
            )
        )

        if admin_count <= 1:
            flash(
                'Ekibin son Admin kullanıcısı çıkarılamaz.',
                'warning'
            )

            return redirect(
                url_for('teams.detail', team_id=team_id)
            )

    removed_username = target_membership.user.username

    db.session.delete(target_membership)
    db.session.commit()

    flash(
        f'{removed_username} ekipten çıkarıldı.',
        'success'
    )

    return redirect(
        url_for('teams.detail', team_id=team_id)
    )