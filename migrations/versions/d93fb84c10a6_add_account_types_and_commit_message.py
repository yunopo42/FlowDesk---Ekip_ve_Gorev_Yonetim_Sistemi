"""add account types and commit message

Revision ID: d93fb84c10a6
Revises: c81e7a403d52
Create Date: 2026-08-06

"""
from alembic import op
import sqlalchemy as sa


revision = 'd93fb84c10a6'
down_revision = 'c81e7a403d52'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'users',
        sa.Column('account_type', sa.String(length=20), nullable=True)
    )

    # Daha önce ekip yöneten kullanıcılar mentör, diğer hesaplar stajyer
    # olarak sınıflandırılır. Böylece mevcut yetkiler korunur.
    op.execute(
        """
        UPDATE users
        SET account_type = 'Mentor'
        WHERE id IN (
            SELECT DISTINCT user_id
            FROM team_members
            WHERE role = 'Admin'
        )
        """
    )
    op.execute(
        """
        UPDATE users
        SET account_type = 'Intern'
        WHERE account_type IS NULL
        """
    )

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column(
            'account_type',
            existing_type=sa.String(length=20),
            nullable=False,
            server_default='Intern'
        )

    op.add_column(
        'task_submissions',
        sa.Column('commit_message', sa.String(length=255), nullable=True)
    )
    op.execute(
        """
        UPDATE task_submissions
        SET commit_message = substr(summary, 1, 255)
        WHERE commit_message IS NULL
        """
    )
    with op.batch_alter_table('task_submissions', schema=None) as batch_op:
        batch_op.alter_column(
            'commit_message',
            existing_type=sa.String(length=255),
            nullable=False
        )


def downgrade():
    with op.batch_alter_table('task_submissions', schema=None) as batch_op:
        batch_op.drop_column('commit_message')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('account_type')
