"""drop unused legacy profile, difficulty, and cached analysis columns

Revision ID: 20260319_0007
Revises: 20260319_0006
Create Date: 2026-03-19 11:15:00
"""

from alembic import op


revision = "20260319_0007"
down_revision = "20260319_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("activity_streams", "interval_analysis")
    op.drop_column("activity_streams", "derived_series")
    op.drop_column("activities", "difficulty_score")
    op.drop_column("period_summaries", "total_difficulty_score")
    op.drop_column("user_profiles", "max_heart_rate_override")
    op.drop_column("user_profiles", "speed_max")
    op.drop_column("user_profiles", "birthday")


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported for dropped legacy columns.")
