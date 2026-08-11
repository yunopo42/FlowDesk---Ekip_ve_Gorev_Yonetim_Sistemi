from datetime import date
from flask import render_template
from flask_login import login_required , current_user
from app.dashboard import dashboard_bp

from app.models import Activity ,Task, TeamMember
from extensions import db

@dashboard_bp.route('/')
@login_required

def index():
    team_ids = db.select(TeamMember.team_id).where(TeamMember.user_id == current_user.id)

    task_query = db.select(Task).where(Task.team_id.in_(team_ids))
    if current_user.is_intern:
        task_query = task_query.where(
            Task.assigned_to_id == current_user.id
        )

    tasks = db.session.scalars(
        task_query.order_by(Task.created_at.desc())
    ).all()

    today = date.today()

    overdue_tasks = [
        task for task in tasks
        if task.due_date and task.due_date.date() < today and task.status != 'Done']
    upcoming_tasks = [
        task for task in tasks
        if task.due_date and task.due_date.date() >= today and task.status != 'Done'
    ]
    upcoming_tasks.sort(key=lambda task : task.due_date)
    upcoming_tasks = upcoming_tasks[:5]
    statistics = {
        'total' : len(tasks),
        'todo' : sum(
            1 for task in tasks
            if task.status == 'Todo'
        ),
        'in_progress' : sum(
            1 for task in tasks
            if task.status == 'In Progress'
        ),
        # İnceleme ve düzeltme durumları da sayılır; aksi halde grafikteki
        # dilimlerin toplamı toplam görev sayısını tutmuyordu.
        'review_pending' : sum(
            1 for task in tasks
            if task.status == 'Review Pending'
        ),
        'revision_requested' : sum(
            1 for task in tasks
            if task.status == 'Revision Requested'
        ),
        'done' : sum(
            1 for task in tasks
            if task.status == 'Done'
        ),
        'overdue' : len(overdue_tasks)
    }
    priority_statistics = {
        'low': sum(
            1 for task in tasks
            if task.priority == 'Low'
        ),
        'medium': sum(
            1 for task in tasks
            if task.priority == 'Medium'
        ),
        'high': sum(
            1 for task in tasks
            if task.priority == 'High'
        )
    }
    recent_tasks = tasks[:5] #ilk 5 taskı çekmeyi sağladı
    activity_query = (
        db.select(Activity)
        .join(Task)
        .where(Task.team_id.in_(team_ids))
    )
    if current_user.is_intern:
        activity_query = activity_query.where(
            Task.assigned_to_id == current_user.id
        )
    recent_activities = db.session.scalars(
        activity_query
        .order_by(Activity.created_at.desc())
        .limit(10)
    ).all()
    # Grafiklerin okuduğu tek veri paketi.
    chart_data = {**statistics, **priority_statistics}

    return render_template(
        'dashboard/index.html',
        statistics=statistics,
        priority_statistics=priority_statistics,
        chart_data=chart_data,
        recent_tasks=recent_tasks,
        upcoming_tasks=upcoming_tasks,
        recent_activities=recent_activities
    )
