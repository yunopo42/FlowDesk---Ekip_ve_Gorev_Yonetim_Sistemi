"""company focused internship fields

Revision ID: c81e7a403d52
Revises: a42d5c931e07
Create Date: 2026-08-06

"""
from alembic import op
import sqlalchemy as sa


revision = 'c81e7a403d52'
down_revision = 'a42d5c931e07'
branch_labels = None
depends_on = None


def upgrade():
    # Kolonları silip yeniden oluşturmak yerine adlarını değiştiriyoruz.
    # Böylece daha önce girilmiş staj kayıtları korunur.
    with op.batch_alter_table('internships', schema=None) as batch_op:
        batch_op.alter_column(
            'school',
            new_column_name='company_unit',
            existing_type=sa.String(length=150),
            existing_nullable=False
        )
        batch_op.alter_column(
            'department',
            new_column_name='internship_role',
            existing_type=sa.String(length=150),
            existing_nullable=False
        )


def downgrade():
    with op.batch_alter_table('internships', schema=None) as batch_op:
        batch_op.alter_column(
            'company_unit',
            new_column_name='school',
            existing_type=sa.String(length=150),
            existing_nullable=False
        )
        batch_op.alter_column(
            'internship_role',
            new_column_name='department',
            existing_type=sa.String(length=150),
            existing_nullable=False
        )
