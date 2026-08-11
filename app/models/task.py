from extensions import db

from app.models.base import utc_now

# Görev durumlarının tek doğruluk kaynağı. Rotalar doğrulama için anahtarları,
# şablonlar ekranda göstermek için Türkçe karşılıklarını kullanır.
TASK_STATUSES = [
    'Todo',
    'In Progress',
    'Review Pending',
    'Revision Requested',
    'Done',
]

TASK_STATUS_LABELS = {
    'Todo': 'Yapılacak',
    'In Progress': 'Devam ediyor',
    'Review Pending': 'İnceleme bekliyor',
    'Revision Requested': 'Düzeltme istendi',
    'Done': 'Tamamlandı',
}

TASK_PRIORITIES = ['Low', 'Medium', 'High']

TASK_PRIORITY_LABELS = {
    'Low': 'Düşük',
    'Medium': 'Orta',
    'High': 'Yüksek',
}


class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)

    # Öncelik: 'Low', 'Medium', 'High'
    priority = db.Column(db.String(20), default='Medium', nullable=False)
    # Durum: 'Todo', 'In Progress', 'Review Pending',
    # 'Revision Requested', 'Done'
    # Gecikme ayrı bir durum değil; is_overdue özelliğinden hesaplanır.
    status = db.Column(db.String(20), default='Todo', nullable=False)

    due_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Yabancı Anahtarlar (Foreign Keys)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    # İlişkiler
    team = db.relationship('Team', back_populates='tasks')
    creator = db.relationship('User', foreign_keys=[created_by_id])
    assignee = db.relationship('User', foreign_keys=[assigned_to_id])
    
    comments = db.relationship('Comment', back_populates='task', cascade='all, delete-orphan')
    activities = db.relationship('Activity', back_populates='task', cascade='all, delete-orphan')
    submissions = db.relationship(
        'TaskSubmission',
        back_populates='task',
        cascade='all, delete-orphan',
        order_by='TaskSubmission.created_at.desc()'
    )

    @property
    def is_overdue(self):
        return bool(
            self.due_date
            and self.status != 'Done'
            and utc_now().date() > self.due_date.date()
        )

    def __repr__(self):
        return f'<Task {self.title}>'
    
class Comment(db.Model):
    __tablename__ = 'comments'

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now)

    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    task = db.relationship('Task', back_populates='comments')
    user = db.relationship('User')

class Activity(db.Model):
    __tablename__ = 'activities'

    id = db.Column(db.Integer, primary_key=True)
    # Örn: 'Görev oluşturuldu', 'Durum değiştirildi'[cite: 1]
    action = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now)

    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    task = db.relationship('Task', back_populates='activities')
    user = db.relationship('User')
