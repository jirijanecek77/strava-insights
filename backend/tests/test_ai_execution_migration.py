from io import StringIO

from alembic.migration import MigrationContext
from alembic.operations import Operations
from test_activity_splits_migration import load_migration


def test_execution_migration_preserves_coaching_and_serializes_all_source_edges():
    output = StringIO()
    operations = Operations(
        MigrationContext.configure(
            dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
        )
    )
    migration = load_migration("20261123_0026_ai_execution.py", operations)
    migration.upgrade()
    sql = output.getvalue()
    assert "CREATE TABLE ai_provider_attempts" in sql
    assert "pg_advisory_xact_lock(74022, athlete)" in sql
    for table in migration.DIRECT + migration.CHILDREN:
        assert f"ON {table} FOR EACH ROW" in sql
    assert "DROP TABLE" not in sql and "TRUNCATE" not in sql
    assert "UPDATE activity_coaching_notes" not in sql
    assert "DELETE FROM" not in sql


def test_source_moves_lock_both_old_and_new_athletes_in_stable_order():
    output = StringIO()
    operations = Operations(
        MigrationContext.configure(
            dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
        )
    )
    load_migration("20261123_0026_ai_execution.py", operations).upgrade()
    sql = output.getvalue()
    assert "to_jsonb(OLD)" in sql and "to_jsonb(NEW)" in sql
    assert "unnest(athletes)" in sql and "ORDER BY" in sql
