"""Persist sync dispatches before publishing them to Celery."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260910_0020"
down_revision = "20260831_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sync_dispatch_outbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "sync_job_id",
            sa.Integer(),
            sa.ForeignKey("sync_jobs.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("sync_type", sa.String(length=50), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_sync_dispatch_outbox_pending",
        "sync_dispatch_outbox",
        ["status", "next_attempt_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_sync_dispatch_outbox_pending", table_name="sync_dispatch_outbox")
    op.drop_table("sync_dispatch_outbox")
