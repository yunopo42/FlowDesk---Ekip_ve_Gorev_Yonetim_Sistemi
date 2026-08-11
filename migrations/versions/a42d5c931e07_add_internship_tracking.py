"""add internship tracking

Revision ID: a42d5c931e07
Revises: 9f6d21c84b7a
Create Date: 2026-08-06

"""
from alembic import op
import sqlalchemy as sa


revision = 'a42d5c931e07'
down_revision = '9f6d21c84b7a'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'internships',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('team_id', sa.Integer(), nullable=False),
        sa.Column('intern_id', sa.Integer(), nullable=False),
        sa.Column('mentor_id', sa.Integer(), nullable=False),
        sa.Column('school', sa.String(length=150), nullable=False),
        sa.Column('department', sa.String(length=150), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='Active', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['intern_id'], ['users.id']),
        sa.ForeignKeyConstraint(['mentor_id'], ['users.id']),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'daily_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('internship_id', sa.Integer(), nullable=False),
        sa.Column('work_date', sa.Date(), nullable=False),
        sa.Column('title', sa.String(length=150), nullable=False),
        sa.Column('work_summary', sa.Text(), nullable=False),
        sa.Column('learned', sa.Text()),
        sa.Column('blockers', sa.Text()),
        sa.Column('hours', sa.Numeric(precision=4, scale=2), nullable=False),
        sa.Column('status', sa.String(length=30), server_default='Submitted', nullable=False),
        sa.Column('mentor_feedback', sa.Text()),
        sa.Column('reviewed_at', sa.DateTime()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['internship_id'], ['internships.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'internship_id',
            'work_date',
            name='uq_daily_log_internship_date'
        )
    )
    op.create_table(
        'task_submissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=False),
        sa.Column('submitted_by_id', sa.Integer(), nullable=False),
        sa.Column('reviewed_by_id', sa.Integer()),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('work_url', sa.String(length=500)),
        sa.Column('challenges', sa.Text()),
        sa.Column('learned', sa.Text()),
        sa.Column('status', sa.String(length=30), server_default='Pending Review', nullable=False),
        sa.Column('mentor_feedback', sa.Text()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('reviewed_at', sa.DateTime()),
        sa.ForeignKeyConstraint(['reviewed_by_id'], ['users.id']),
        sa.ForeignKeyConstraint(['submitted_by_id'], ['users.id']),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id']),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('task_submissions')
    op.drop_table('daily_logs')
    op.drop_table('internships')
