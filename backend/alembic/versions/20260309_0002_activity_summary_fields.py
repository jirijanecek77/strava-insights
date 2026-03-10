"""add activity summary fields

Revision ID: 20260309_0002
Revises: 20260309_0001
Create Date: 2026-03-09 19:10:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260309_0002"
down_revision = "20260309_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("activities", sa.Column("distance_km", sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column("activities", sa.Column("moving_time_display", sa.String(length=32), nullable=True))
    op.add_column("activities", sa.Column("average_speed_kph", sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column("activities", sa.Column("average_pace_seconds_per_km", sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column("activities", sa.Column("average_pace_display", sa.String(length=16), nullable=True))
    op.add_column("activities", sa.Column("summary_metric_display", sa.String(length=32), nullable=True))
    op.add_column("activities", sa.Column("difficulty_score", sa.Numeric(precision=12, scale=4), nullable=True))


def downgrade() -> None:
    op.drop_column("activities", "difficulty_score")
    op.drop_column("activities", "summary_metric_display")
    op.drop_column("activities", "average_pace_display")
    op.drop_column("activities", "average_pace_seconds_per_km")
    op.drop_column("activities", "average_speed_kph")
    op.drop_column("activities", "moving_time_display")
    op.drop_column("activities", "distance_km")
