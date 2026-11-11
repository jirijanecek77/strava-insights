"""Persist recorded Garmin laps and durable split-fetch work without changing activity data."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20261111_0023"
down_revision = "20261110_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "activity_splits",
        sa.Column("activity_id", sa.Integer(), sa.ForeignKey("activities.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("laps", JSONB(), nullable=False, server_default="[]"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("fetched_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_activity_splits_pending", "activity_splits", ["status", "next_attempt_at"])


def downgrade() -> None:
    op.drop_table("activity_splits")
