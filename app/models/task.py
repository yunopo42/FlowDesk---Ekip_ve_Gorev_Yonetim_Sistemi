from extensions import db
from datetime import datetime

class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)

    # Öncelik: 'Low', 'Medium', 'High'
    priority = db.Column(db.String(20), default='Medium', nullable=False)
    # Durum: 'Todo', 'In Progress', 'Done', 'Overdue'
    status = db.Column(db.String(20), default='Todo', nullable=False)

    due_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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

    def __repr__(self):
        return f'<Task {self.title}>'
    
class Comment(db.Model):
    __tablename__ = 'comments'

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    task = db.relationship('Task', back_populates='comments')
    user = db.relationship('User')

class Activity(db.Model):
    __tablename__ = 'activities'

    id = db.Column(db.Integer, primary_key=True)
    # Örn: 'Görev oluşturuldu', 'Durum değiştirildi'[cite: 1]
    action = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    task = db.relationship('Task', back_populates='activities')
    user = db.relationship('User')