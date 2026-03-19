"""add dated threshold history

Revision ID: 20260319_0008
Revises: 20260319_0007
Create Date: 2026-03-19 09:45:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260319_0008"
down_revision = "20260319_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_threshold_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("aet_heart_rate_bpm", sa.Integer(), nullable=True),
        sa.Column("ant_heart_rate_bpm", sa.Integer(), nullable=True),
        sa.Column("aet_pace_min_per_km", sa.Numeric(5, 2), nullable=True),
        sa.Column("ant_pace_min_per_km", sa.Numeric(5, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "effective_from", name="uq_user_threshold_profiles_user_date"),
    )

    op.execute(
        """
        INSERT INTO user_threshold_profiles (
            user_id,
            effective_from,
            aet_heart_rate_bpm,
            ant_heart_rate_bpm,
            aet_pace_min_per_km,
            ant_pace_min_per_km,
            created_at,
            updated_at
        )
        SELECT
            user_id,
            DATE '1900-01-01',
            aet_heart_rate_bpm,
            ant_heart_rate_bpm,
            aet_pace_min_per_km,
            ant_pace_min_per_km,
            NOW(),
            NOW()
        FROM user_profiles
        WHERE
            aet_heart_rate_bpm IS NOT NULL
            OR ant_heart_rate_bpm IS NOT NULL
            OR aet_pace_min_per_km IS NOT NULL
            OR ant_pace_min_per_km IS NOT NULL
        """
    )


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported for threshold history migration.")
