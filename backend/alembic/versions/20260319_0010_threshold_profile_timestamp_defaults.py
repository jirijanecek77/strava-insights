"""add timestamp defaults for threshold profiles

Revision ID: 20260319_0010
Revises: 20260319_0009
Create Date: 2026-03-19 11:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260319_0010"
down_revision = "20260319_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "user_threshold_profiles",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        existing_nullable=False,
    )
    op.alter_column(
        "user_threshold_profiles",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        existing_nullable=False,
    )


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported for threshold profile timestamp defaults.")
