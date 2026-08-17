"""remove premium route comparison storage

Revision ID: 20260810_0015
Revises: 20260810_0014
Create Date: 2026-08-10
"""

import sqlalchemy as sa

from alembic import op

revision = "20260810_0015"
down_revision = "20260810_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_activities_user_route_sport_time", table_name="activities")
    op.drop_column("activities", "intervals_route_name")
    op.drop_column("activities", "intervals_route_id")


def downgrade() -> None:
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
