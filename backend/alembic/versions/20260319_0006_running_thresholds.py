"""add explicit running threshold fields to user profiles

Revision ID: 20260319_0006
Revises: 20260316_0005
Create Date: 2026-03-19 09:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260319_0006"
down_revision = "20260316_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_profiles", sa.Column("aet_heart_rate_bpm", sa.Integer(), nullable=True))
    op.add_column("user_profiles", sa.Column("ant_heart_rate_bpm", sa.Integer(), nullable=True))
    op.add_column("user_profiles", sa.Column("aet_pace_min_per_km", sa.Numeric(precision=5, scale=2), nullable=True))
    op.add_column("user_profiles", sa.Column("ant_pace_min_per_km", sa.Numeric(precision=5, scale=2), nullable=True))


def downgrade() -> None:
    op.drop_column("user_profiles", "ant_pace_min_per_km")
    op.drop_column("user_profiles", "aet_pace_min_per_km")
    op.drop_column("user_profiles", "ant_heart_rate_bpm")
    op.drop_column("user_profiles", "aet_heart_rate_bpm")
