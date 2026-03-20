"""add user-scoped strava app credentials

Revision ID: 20260320_0011
Revises: 20260319_0010
Create Date: 2026-03-20 13:15:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260320_0011"
down_revision = "20260319_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_strava_app_credentials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("client_secret_encrypted", sa.String(length=4096), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_user_strava_app_credentials_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_strava_app_credentials")),
        sa.UniqueConstraint("user_id", name=op.f("uq_user_strava_app_credentials_user_id")),
    )
    op.create_table(
        "strava_oauth_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("state_token", sa.String(length=255), nullable=False),
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("client_secret_encrypted", sa.String(length=4096), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_strava_oauth_states")),
        sa.UniqueConstraint("state_token", name=op.f("uq_strava_oauth_states_state_token")),
    )


def downgrade() -> None:
    op.drop_table("strava_oauth_states")
    op.drop_table("user_strava_app_credentials")
