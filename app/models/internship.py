from extensions import db

from app.models.base import utc_now

INTERNSHIP_STATUS_LABELS = {
    'Planned': 'Planlandı',
    'Active': 'Aktif',
    'Completed': 'Tamamlandı',
    'Cancelled': 'İptal edildi',
}

REVIEW_STATUS_LABELS = {
    'Submitted': 'İnceleme bekliyor',
    'Pending Review': 'İnceleme bekliyor',
    'Approved': 'Onaylandı',
    'Revision Requested': 'Düzeltme istendi',
}


class Internship(db.Model):
    __tablename__ = 'internships'

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(
        db.Integer,
        db.ForeignKey('teams.id'),
        nullable=False
    )
    intern_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id'),
        nullable=False
    )
    mentor_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id'),
        nullable=False
    )
    company_unit = db.Column(db.String(150), nullable=False)
    internship_role = db.Column(db.String(150), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='Active', nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    team = db.relationship('Team')
    intern = db.relationship('User', foreign_keys=[intern_id])
    mentor = db.relationship('User', foreign_keys=[mentor_id])
    daily_logs = db.relationship(
        'DailyLog',
        back_populates='internship',
        cascade='all, delete-orphan'
    )


class DailyLog(db.Model):
    __tablename__ = 'daily_logs'
    __table_args__ = (
        db.UniqueConstraint(
            'internship_id',
            'work_date',
            name='uq_daily_log_internship_date'
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    internship_id = db.Column(
        db.Integer,
        db.ForeignKey('internships.id'),
        nullable=False
    )
    work_date = db.Column(db.Date, nullable=False)
    title = db.Column(db.String(150), nullable=False)
    work_summary = db.Column(db.Text, nullable=False)
    learned = db.Column(db.Text)
    blockers = db.Column(db.Text)
    hours = db.Column(db.Numeric(4, 2), nullable=False)
    status = db.Column(db.String(30), default='Submitted', nullable=False)
    mentor_feedback = db.Column(db.Text)
    reviewed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=utc_now,
        onupdate=utc_now,
        nullable=False
    )

    internship = db.relationship('Internship', back_populates='daily_logs')


class TaskSubmission(db.Model):
    __tablename__ = 'task_submissions'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(
        db.Integer,
        db.ForeignKey('tasks.id'),
        nullable=False
    )
    submitted_by_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id'),
        nullable=False
    )
    reviewed_by_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id')
    )
    summary = db.Column(db.Text, nullable=False)
    commit_message = db.Column(db.String(255), nullable=False)
    work_url = db.Column(db.String(500))
    challenges = db.Column(db.Text)
    learned = db.Column(db.Text)
    status = db.Column(
        db.String(30),
        default='Pending Review',
        nullable=False
    )
    mentor_feedback = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    reviewed_at = db.Column(db.DateTime)

    task = db.relationship('Task', back_populates='submissions')
    submitted_by = db.relationship(
        'User',
        foreign_keys=[submitted_by_id]
    )
    reviewed_by = db.relationship(
        'User',
        foreign_keys=[reviewed_by_id]
    )

    @property
    def is_late(self):
        return bool(
            self.task.due_date
            and self.created_at.date() > self.task.due_date.date()
        )
