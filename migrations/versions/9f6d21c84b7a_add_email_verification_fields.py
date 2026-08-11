"""add email verification fields

Revision ID: 9f6d21c84b7a
Revises: 0433db930b45
Create Date: 2026-07-17

"""
from alembic import op
import sqlalchemy as sa


revision = '9f6d21c84b7a'
down_revision = '0433db930b45'
branch_labels = None
depends_on = None


def upgrade():
    # Varsayılan True sayesinde daha önce oluşturulmuş kullanıcıların
    # uygulamaya erişimi kesilmez.
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'email_verified',
                sa.Boolean(),
                server_default=sa.true(),
                nullable=False
            )
        )
        batch_op.add_column(
            sa.Column('email_verified_at', sa.DateTime(), nullable=True)
        )


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('email_verified_at')
        batch_op.drop_column('email_verified')
