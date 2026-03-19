"""add heart rate drift kpi to activities

Revision ID: 20260316_0004
Revises: 20260310_0003
Create Date: 2026-03-16 12:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260316_0004"
down_revision = "20260310_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("activities", sa.Column("heart_rate_drift_bpm", sa.Numeric(precision=6, scale=2), nullable=True))


def downgrade() -> None:
    op.drop_column("activities", "heart_rate_drift_bpm")
