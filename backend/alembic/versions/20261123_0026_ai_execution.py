"""Fence AI work and record actual provider attempts without replacing saved coaching."""

import sqlalchemy as sa
from alembic import op

revision = "20261123_0026"
down_revision = "20261113_0025"
branch_labels = None
depends_on = None

# All source mutations share the publisher's athlete transaction lock, including
# writes made through a backend/import/CLI path that does not know about AI.
DIRECT = (
    "users",
    "activities",
    "user_threshold_profiles",
    "activity_coaching_notes",
    "period_coaching_summaries",
    "sync_jobs",
    "best_efforts",
    "training_plan_requests",
)
CHILDREN = (
    "activity_streams",
    "activity_splits",
    "activity_coaching_evidence",
    "activity_route_memberships",
)


def upgrade():
    for table in ("activity_coaching_notes", "period_coaching_summaries"):
        op.add_column(table, sa.Column("lease_token", sa.String(36), nullable=True))
    for table in (
        "activity_coaching_notes",
        "period_coaching_summaries",
        "training_plan_requests",
    ):
        op.add_column(table, sa.Column("input_revision", sa.String(64), nullable=True))
    op.create_table(
        "ai_provider_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("operation", sa.String(20), nullable=False),
        sa.Column("work_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("lease_token", sa.String(36), nullable=False),
        sa.Column("input_revision", sa.String(64), nullable=False),
        sa.Column("prompt_fingerprint", sa.String(64), nullable=False),
        sa.Column("prompt_version", sa.String(20), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("usage", sa.JSON(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "operation", "work_id", "lease_token", name="uq_ai_attempt_claim"
        ),
    )
    op.create_index(
        "ix_ai_attempts_work",
        "ai_provider_attempts",
        ["operation", "work_id", "started_at"],
    )
    op.execute("""
    CREATE FUNCTION ai_lock_source() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE row_data jsonb; athlete integer; activity integer; athletes integer[] := '{}'; records jsonb[];
    BEGIN
      IF TG_OP = 'INSERT' THEN records := ARRAY[to_jsonb(NEW)];
      ELSIF TG_OP = 'DELETE' THEN records := ARRAY[to_jsonb(OLD)];
      ELSE records := ARRAY[to_jsonb(OLD), to_jsonb(NEW)]; END IF;
      FOREACH row_data IN ARRAY records LOOP
        IF TG_TABLE_NAME = 'users' THEN athlete := (row_data->>'id')::integer;
        ELSIF row_data ? 'user_id' THEN athlete := (row_data->>'user_id')::integer;
        ELSE
          activity := (row_data->>'activity_id')::integer;
          SELECT user_id INTO athlete FROM activities WHERE id = activity;
        END IF;
        athletes := array_append(athletes, athlete);
      END LOOP;
      FOR athlete IN SELECT DISTINCT value FROM unnest(athletes) value WHERE value IS NOT NULL ORDER BY value LOOP
        PERFORM pg_advisory_xact_lock(74022, athlete);
      END LOOP;
      IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
    END $$;
    """)
    for table in DIRECT + CHILDREN:
        op.execute(
            f"CREATE TRIGGER ai_source_serialization BEFORE INSERT OR UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION ai_lock_source()"
        )


def downgrade():
    for table in DIRECT + CHILDREN:
        op.execute(f"DROP TRIGGER ai_source_serialization ON {table}")
    op.execute("DROP FUNCTION ai_lock_source()")
    op.drop_table("ai_provider_attempts")
    for table in (
        "activity_coaching_notes",
        "period_coaching_summaries",
        "training_plan_requests",
    ):
        op.drop_column(table, "input_revision")
    for table in ("activity_coaching_notes", "period_coaching_summaries"):
        op.drop_column(table, "lease_token")
