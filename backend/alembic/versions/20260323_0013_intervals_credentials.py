"""replace legacy strava auth storage with intervals credentials

Revision ID: 20260323_0013
Revises: 20260323_0012
Create Date: 2026-03-23 14:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "20260323_0013"
down_revision = "20260323_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "intervals_credentials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("athlete_id", sa.String(length=255), nullable=False),
        sa.Column("api_key_encrypted", sa.String(length=4096), nullable=False),
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
            ["user_id"],
            ["users.id"],
            name=op.f("fk_intervals_credentials_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_intervals_credentials")),
        sa.UniqueConstraint("user_id", name=op.f("uq_intervals_credentials_user_id")),
    )

    op.execute("""
        INSERT INTO intervals_credentials (user_id, athlete_id, api_key_encrypted, created_at, updated_at)
        SELECT user_id, client_id, client_secret_encrypted, created_at, updated_at
        FROM user_strava_app_credentials
        ON CONFLICT (user_id) DO NOTHING
        """)
    op.execute("""
        INSERT INTO intervals_credentials (user_id, athlete_id, api_key_encrypted, created_at, updated_at)
        SELECT user_id, strava_athlete_id::text, access_token_encrypted, created_at, updated_at
        FROM oauth_tokens
        WHERE provider = 'intervals_icu' AND strava_athlete_id IS NOT NULL
        ON CONFLICT (user_id) DO NOTHING
        """)

    op.drop_table("strava_oauth_states")
    op.drop_table("user_strava_app_credentials")
    op.drop_table("oauth_tokens")


def downgrade() -> None:
    op.create_table(
        "oauth_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("access_token_encrypted", sa.String(length=2048), nullable=False),
        sa.Column("refresh_token_encrypted", sa.String(length=2048), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scope", sa.String(length=255), nullable=True),
        sa.Column("strava_athlete_id", sa.BigInteger(), nullable=True),
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
            ["user_id"], ["users.id"], name=op.f("fk_oauth_tokens_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth_tokens")),
        sa.UniqueConstraint(
            "user_id", "provider", name="uq_oauth_tokens_user_provider"
        ),
    )
    op.create_table(
        "user_strava_app_credentials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("client_secret_encrypted", sa.String(length=4096), nullable=False),
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
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_strava_app_credentials_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_strava_app_credentials")),
        sa.UniqueConstraint(
            "user_id", name=op.f("uq_user_strava_app_credentials_user_id")
        ),
    )
    op.create_table(
        "strava_oauth_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("state_token", sa.String(length=255), nullable=False),
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("client_secret_encrypted", sa.String(length=4096), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_strava_oauth_states")),
        sa.UniqueConstraint(
            "state_token", name=op.f("uq_strava_oauth_states_state_token")
        ),
    )
    op.execute("""
        INSERT INTO user_strava_app_credentials (user_id, client_id, client_secret_encrypted, created_at, updated_at)
        SELECT user_id, athlete_id, api_key_encrypted, created_at, updated_at
        FROM intervals_credentials
        """)
    op.execute("""
        INSERT INTO oauth_tokens (
            user_id, provider, access_token_encrypted, refresh_token_encrypted,
            expires_at, scope, strava_athlete_id, created_at, updated_at
        )
        SELECT
            user_id, 'intervals_icu', api_key_encrypted, api_key_encrypted,
            '9999-12-31 23:59:59+00', 'ACTIVITY:READ',
            athlete_id::bigint, created_at, updated_at
        FROM intervals_credentials
        WHERE athlete_id ~ '^[0-9]+$'
        """)
    op.drop_table("intervals_credentials")
