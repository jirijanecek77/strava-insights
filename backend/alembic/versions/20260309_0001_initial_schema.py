"""initial schema

Revision ID: 20260309_0001
Revises: None
Create Date: 2026-03-09 15:45:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260309_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("strava_athlete_id", sa.BigInteger(), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("profile_picture_url", sa.String(length=1024), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("strava_athlete_id", name=op.f("uq_users_strava_athlete_id")),
    )
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("birthday", sa.Date(), nullable=True),
        sa.Column("speed_max", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("max_heart_rate_override", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_user_profiles_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_profiles")),
        sa.UniqueConstraint("user_id", name=op.f("uq_user_profiles_user_id")),
    )
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
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_oauth_tokens_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth_tokens")),
        sa.UniqueConstraint("user_id", "provider", name="uq_oauth_tokens_user_provider"),
    )
    op.create_table(
        "activities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("strava_activity_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sport_type", sa.String(length=50), nullable=False),
        sa.Column("start_date_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("start_date_local", sa.DateTime(timezone=True), nullable=True),
        sa.Column("distance_meters", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("moving_time_seconds", sa.Integer(), nullable=False),
        sa.Column("elapsed_time_seconds", sa.Integer(), nullable=True),
        sa.Column("total_elevation_gain_meters", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("elev_high_meters", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("elev_low_meters", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("average_speed_mps", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("max_speed_mps", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("average_heartrate_bpm", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("max_heartrate_bpm", sa.Integer(), nullable=True),
        sa.Column("average_cadence", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("start_latlng", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_activities_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_activities")),
        sa.UniqueConstraint("strava_activity_id", name=op.f("uq_activities_strava_activity_id")),
    )
    op.create_index("ix_activities_user_start_date_desc", "activities", ["user_id", "start_date_utc"], unique=False)
    op.create_index(
        "ix_activities_user_sport_start_date_desc",
        "activities",
        ["user_id", "sport_type", "start_date_utc"],
        unique=False,
    )
    op.create_table(
        "activity_streams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.Column("time_stream", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("distance_stream", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("latlng_stream", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("altitude_stream", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("velocity_smooth_stream", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("heartrate_stream", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("derived_series", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("interval_analysis", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["activity_id"], ["activities.id"], name=op.f("fk_activity_streams_activity_id_activities")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_activity_streams")),
        sa.UniqueConstraint("activity_id", name=op.f("uq_activity_streams_activity_id")),
    )
    op.create_table(
        "period_summaries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("sport_type", sa.String(length=50), nullable=False),
        sa.Column("period_type", sa.String(length=20), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("activity_count", sa.Integer(), nullable=False),
        sa.Column("total_distance_meters", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("total_moving_time_seconds", sa.Integer(), nullable=False),
        sa.Column("average_speed_mps", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("average_pace_seconds_per_km", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("total_elevation_gain_meters", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("total_difficulty_score", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_period_summaries_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_period_summaries")),
    )
    op.create_index(
        "ix_period_summaries_user_sport_period",
        "period_summaries",
        ["user_id", "sport_type", "period_type", "period_start"],
        unique=False,
    )
    op.create_table(
        "best_efforts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("sport_type", sa.String(length=50), nullable=False),
        sa.Column("effort_code", sa.String(length=50), nullable=False),
        sa.Column("best_time_seconds", sa.Integer(), nullable=False),
        sa.Column("distance_meters", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("activity_id", sa.Integer(), nullable=True),
        sa.Column("achieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["activity_id"], ["activities.id"], name=op.f("fk_best_efforts_activity_id_activities")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_best_efforts_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_best_efforts")),
    )
    op.create_index("ix_best_efforts_user_sport_effort_code", "best_efforts", ["user_id", "sport_type", "effort_code"], unique=False)
    op.create_table(
        "activity_best_efforts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.Column("effort_code", sa.String(length=50), nullable=False),
        sa.Column("best_time_seconds", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["activity_id"], ["activities.id"], name=op.f("fk_activity_best_efforts_activity_id_activities")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_activity_best_efforts")),
    )
    op.create_table(
        "sync_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("sync_type", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("progress_total", sa.Integer(), nullable=True),
        sa.Column("progress_completed", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_sync_jobs_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sync_jobs")),
    )
    op.create_table(
        "sync_checkpoints",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("sync_type", sa.String(length=50), nullable=False),
        sa.Column("checkpoint_value", sa.String(length=255), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_sync_checkpoints_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sync_checkpoints")),
    )


def downgrade() -> None:
    op.drop_table("sync_checkpoints")
    op.drop_table("sync_jobs")
    op.drop_table("activity_best_efforts")
    op.drop_index("ix_best_efforts_user_sport_effort_code", table_name="best_efforts")
    op.drop_table("best_efforts")
    op.drop_index("ix_period_summaries_user_sport_period", table_name="period_summaries")
    op.drop_table("period_summaries")
    op.drop_table("activity_streams")
    op.drop_index("ix_activities_user_sport_start_date_desc", table_name="activities")
    op.drop_index("ix_activities_user_start_date_desc", table_name="activities")
    op.drop_table("activities")
    op.drop_table("oauth_tokens")
    op.drop_table("user_profiles")
    op.drop_table("users")
