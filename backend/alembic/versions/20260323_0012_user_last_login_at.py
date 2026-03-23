"""add last login timestamp to users

Revision ID: 20260323_0012
Revises: 20260320_0011
Create Date: 2026-03-23 10:45:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260323_0012"
down_revision = "20260320_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "last_login_at")
