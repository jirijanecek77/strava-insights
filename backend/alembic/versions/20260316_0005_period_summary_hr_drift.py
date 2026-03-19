"""add average heart rate drift to period summaries

Revision ID: 20260316_0005
Revises: 20260316_0004
Create Date: 2026-03-16 12:35:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260316_0005"
down_revision = "20260316_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("period_summaries", sa.Column("average_heart_rate_drift_bpm", sa.Numeric(precision=10, scale=2), nullable=True))


def downgrade() -> None:
    op.drop_column("period_summaries", "average_heart_rate_drift_bpm")
