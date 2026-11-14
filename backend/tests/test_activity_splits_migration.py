"""Verify the migration's safety contract using offline SQL generation, with no database."""

import importlib.util
from io import StringIO
from pathlib import Path
from unittest.mock import Mock

from alembic.migration import MigrationContext
from alembic.operations import Operations


def load_migration(filename, operations):
    path = Path(__file__).parents[1] / "alembic" / "versions" / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = operations
    return module


def test_cleanup_only_updates_pending_status_and_removes_queue_columns():
    operations = Mock()
    migration = load_migration("20261111_0024_inline_activity_splits.py", operations)
    migration.upgrade()
    sql = operations.execute.call_args.args[0]
    assert "WHERE status = 'pending'" in sql
    assert "jsonb_array_length(laps)" in sql
    assert "THEN 'ready' ELSE 'unavailable'" in sql
    assert {call.args[1] for call in operations.drop_column.call_args_list} == {
        "version",
        "attempt_count",
        "next_attempt_at",
        "fetched_at",
    }
    assert all(
        call.args[0] == "activity_splits"
        for call in operations.drop_column.call_args_list
    )
    operations.drop_table.assert_not_called()
    operations.alter_column.assert_called_once_with(
        "activity_splits", "status", server_default="unavailable"
    )


def test_upgrade_and_downgrade_compile_offline_without_replacing_lap_data():
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
    )
    migration = load_migration(
        "20261111_0024_inline_activity_splits.py", Operations(context)
    )
    migration.upgrade()
    migration.downgrade()
    sql = output.getvalue()
    assert "ALTER TABLE activity_splits" in sql
    assert "CREATE INDEX ix_activity_splits_pending" in sql
    assert "DELETE" not in sql and "TRUNCATE" not in sql and "DROP TABLE" not in sql
    assert "DROP COLUMN laps" not in sql and "SET laps" not in sql
