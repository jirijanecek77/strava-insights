"""rename active source fields and migrate credentials to Garmin"""

import sqlalchemy as sa
from alembic import op

revision = "20260826_0017"
down_revision = "20260817_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("users", "strava_athlete_id", new_column_name="external_user_id")
    op.alter_column("activities", "strava_activity_id", new_column_name="source_activity_id")
    op.drop_constraint("uq_users_strava_athlete_id", "users", type_="unique")
    op.drop_constraint("uq_activities_strava_activity_id", "activities", type_="unique")
    op.add_column("users", sa.Column("source_provider", sa.String(32), nullable=True))
    op.add_column("activities", sa.Column("source_provider", sa.String(32), nullable=True))
    op.execute("UPDATE users SET source_provider = 'legacy' WHERE source_provider IS NULL")
    op.execute("UPDATE activities SET source_provider = 'legacy' WHERE source_provider IS NULL")
    op.alter_column("users", "source_provider", nullable=False)
    op.alter_column("activities", "source_provider", nullable=False)
    op.create_unique_constraint("uq_users_source_provider_external_user", "users", ["source_provider", "external_user_id"])
    op.create_unique_constraint("uq_activities_user_provider_source", "activities", ["user_id", "source_provider", "source_activity_id"])
    op.create_table(
        "garmin_credentials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("email_encrypted", sa.String(4096), nullable=False),
        sa.Column("token_json_encrypted", sa.String(16384), nullable=False),
        sa.Column("external_user_id", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("garmin_credentials")
    op.drop_constraint("uq_activities_user_provider_source", "activities", type_="unique")
    op.drop_constraint("uq_users_source_provider_external_user", "users", type_="unique")
    op.drop_column("activities", "source_provider")
    op.drop_column("users", "source_provider")
    op.alter_column("activities", "source_activity_id", new_column_name="strava_activity_id")
    op.alter_column("users", "external_user_id", new_column_name="strava_athlete_id")
    op.create_unique_constraint("uq_activities_strava_activity_id", "activities", ["strava_activity_id"])
    op.create_unique_constraint("uq_users_strava_athlete_id", "users", ["strava_athlete_id"])
