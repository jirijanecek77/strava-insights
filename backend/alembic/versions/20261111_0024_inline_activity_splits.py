"""Retain recorded laps while removing the separate split-fetch queue."""

import sqlalchemy as sa
from alembic import op

revision = "20261111_0024"
down_revision = "20261111_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE activity_splits
        SET status = CASE WHEN jsonb_array_length(laps) > 0 THEN 'ready' ELSE 'unavailable' END
        WHERE status = 'pending'
    """)
    op.alter_column("activity_splits", "status", server_default="unavailable")
    op.drop_index("ix_activity_splits_pending", table_name="activity_splits")
    for column in ("version", "attempt_count", "next_attempt_at", "fetched_at"):
        op.drop_column("activity_splits", column)


def downgrade() -> None:
    op.add_column("activity_splits", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("activity_splits", sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("activity_splits", sa.Column("next_attempt_at", sa.DateTime(timezone=True)))
    op.add_column("activity_splits", sa.Column("fetched_at", sa.DateTime(timezone=True)))
    op.alter_column("activity_splits", "status", server_default="pending")
    op.create_index("ix_activity_splits_pending", "activity_splits", ["status", "next_attempt_at"])
