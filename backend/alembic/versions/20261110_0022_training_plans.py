"""Add durable AI running-plan requests and daily targets without changing activity data."""

import sqlalchemy as sa
from alembic import op

revision = "20261110_0022"
down_revision = "20261011_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "training_plan_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("sync_job_id", sa.Integer(), sa.ForeignKey("sync_jobs.id")),
        sa.Column("source_key", sa.String(100), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("target_start", sa.Date()),
        sa.Column("context_json", sa.JSON()),
        sa.Column("source_hash", sa.String(64)),
        sa.Column("model", sa.String(100)),
        sa.Column("prompt_version", sa.String(20)),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("lease_token", sa.String(36)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column("generated_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "user_id", "source_key", name="uq_training_plan_request_source"
        ),
    )
    op.create_index(
        "ix_training_plan_requests_pending",
        "training_plan_requests",
        ["status", "next_attempt_at", "id"],
    )
    op.create_index(
        "ix_training_plan_requests_user", "training_plan_requests", ["user_id", "id"]
    )
    op.create_table(
        "training_plan_days",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "request_id",
            sa.Integer(),
            sa.ForeignKey("training_plan_requests.id"),
            nullable=False,
        ),
        sa.Column("planned_date", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("focus", sa.String(20), nullable=False),
        sa.Column("distance_meters", sa.Numeric(10, 2)),
        sa.Column("pace_seconds_per_km", sa.Integer()),
        sa.Column("heart_rate_bpm", sa.Integer()),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "user_id", "planned_date", name="uq_training_plan_day_user_date"
        ),
        sa.CheckConstraint(
            "(kind = 'rest' AND distance_meters IS NULL AND pace_seconds_per_km IS NULL AND heart_rate_bpm IS NULL) OR (kind = 'run' AND distance_meters > 0 AND pace_seconds_per_km > 0 AND heart_rate_bpm > 0 AND distance_meters IS NOT NULL AND pace_seconds_per_km IS NOT NULL AND heart_rate_bpm IS NOT NULL)",
            name="ck_training_plan_day_targets",
        ),
    )


def downgrade() -> None:
    op.drop_table("training_plan_days")
    op.drop_table("training_plan_requests")
