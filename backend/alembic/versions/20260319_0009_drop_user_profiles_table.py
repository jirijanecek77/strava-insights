"""drop obsolete user_profiles table

Revision ID: 20260319_0009
Revises: 20260319_0008
Create Date: 2026-03-19 10:05:00
"""

from alembic import op


revision = "20260319_0009"
down_revision = "20260319_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("user_profiles")


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported for dropping the obsolete user_profiles table.")
