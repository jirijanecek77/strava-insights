"""clean up activity analytics storage and add Intervals routes

Revision ID: 20260810_0014
Revises: 20260323_0013
Create Date: 2026-08-10 12:00:00
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260810_0014"
down_revision = "20260323_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "activities",
        sa.Column("intervals_route_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "activities",
        sa.Column("intervals_route_name", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_activities_user_route_sport_time",
        "activities",
        ["user_id", "intervals_route_id", "sport_type", "moving_time_seconds"],
        unique=False,
    )

    op.drop_table("activity_best_efforts")
    op.drop_column("period_summaries", "average_heart_rate_drift_bpm")
    op.drop_column("activities", "heart_rate_drift_bpm")
    op.drop_column("activities", "elev_high_meters")
    op.drop_column("activities", "elev_low_meters")
    op.drop_column("activities", "max_heartrate_bpm")
    op.drop_column("activities", "start_latlng")
    op.drop_column("users", "email")


def downgrade() -> None:
    op.add_column("users", sa.Column("email", sa.String(length=320), nullable=True))
    op.add_column(
        "activities",
        sa.Column(
            "start_latlng", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )
    op.add_column(
        "activities", sa.Column("max_heartrate_bpm", sa.Integer(), nullable=True)
    )
    op.add_column(
        "activities",
        sa.Column("elev_low_meters", sa.Numeric(precision=10, scale=2), nullable=True),
    )
    op.add_column(
        "activities",
        sa.Column("elev_high_meters", sa.Numeric(precision=10, scale=2), nullable=True),
    )
    op.add_column(
        "activities",
        sa.Column(
            "heart_rate_drift_bpm", sa.Numeric(precision=6, scale=2), nullable=True
        ),
    )
    op.add_column(
        "period_summaries",
        sa.Column(
            "average_heart_rate_drift_bpm",
            sa.Numeric(precision=10, scale=2),
            nullable=True,
        ),
    )
    op.create_table(
        "activity_best_efforts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.Column("effort_code", sa.String(length=50), nullable=False),
        sa.Column("best_time_seconds", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["activity_id"],
            ["activities.id"],
            name=op.f("fk_activity_best_efforts_activity_id_activities"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_activity_best_efforts")),
    )

    op.drop_index("ix_activities_user_route_sport_time", table_name="activities")
    op.drop_column("activities", "intervals_route_name")
    op.drop_column("activities", "intervals_route_id")
