"""separate personnel team and mentor roles

Revision ID: e27ca61b9054
Revises: d93fb84c10a6
Create Date: 2026-08-06

"""
from alembic import op


revision = 'e27ca61b9054'
down_revision = 'd93fb84c10a6'
branch_labels = None
depends_on = None


def upgrade():
    # Personel bir hesap türüdür; mentörlük Internship.mentor_id üzerinden
    # belirlenen ayrı bir ilişkidir.
    op.execute(
        """
        UPDATE users
        SET account_type = 'Personnel'
        WHERE account_type = 'Mentor'
        """
    )

    # Stajyerlerin ekip rolü normal yazılım personeli Member rolünden ayrılır.
    op.execute(
        """
        UPDATE team_members
        SET role = 'Intern'
        WHERE role = 'Member'
          AND user_id IN (
              SELECT id FROM users WHERE account_type = 'Intern'
          )
        """
    )


def downgrade():
    op.execute(
        """
        UPDATE team_members
        SET role = 'Member'
        WHERE role = 'Intern'
        """
    )
    op.execute(
        """
        UPDATE users
        SET account_type = 'Mentor'
        WHERE account_type = 'Personnel'
        """
    )
