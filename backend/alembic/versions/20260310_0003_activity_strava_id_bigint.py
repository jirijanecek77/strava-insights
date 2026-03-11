"""ensure activity strava id uses bigint

Revision ID: 20260310_0003
Revises: 20260309_0002
Create Date: 2026-03-10 14:10:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260310_0003"
down_revision = "20260309_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "activities",
        "strava_activity_id",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "activities",
        "strava_activity_id",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
    )
