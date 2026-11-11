"""Exercise schema cleanup against real PostgreSQL while preserving recorded data."""

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text


def load_migration(filename, operations):
    path = Path(__file__).parents[1] / "alembic" / "versions" / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = operations
    return module


def test_cleanup_preserves_laps_and_finalizes_pending_rows(db_session):
    with db_session.bind.connect() as connection, connection.begin():
        # A separate transactional schema keeps the migration independent of the current ORM.
        connection.execute(text("CREATE SCHEMA pytest_splits_migration"))
        connection.execute(text("SET LOCAL search_path TO pytest_splits_migration"))
        connection.execute(text("CREATE TABLE activities (id integer PRIMARY KEY)"))
        operations = Operations(MigrationContext.configure(connection))
        original = load_migration("20261111_0023_activity_splits.py", operations)
        cleanup = load_migration("20261111_0024_inline_activity_splits.py", operations)
        original.upgrade()
        connection.execute(text("INSERT INTO activities VALUES (1), (2), (3), (4)"))
        connection.execute(text("""
            INSERT INTO activity_splits (activity_id, status, laps, attempt_count)
            VALUES (1, 'ready', '[{"number": 1,"average_heartrate_bpm": 145}]', 2),
                   (2, 'pending', '[]', 3), (3, 'pending', '[{"number": 2}]', 1),
                   (4, 'unavailable', '[]', 0)
        """))
        before = connection.execute(text("SELECT activity_id, laps FROM activity_splits ORDER BY activity_id")).all()
        cleanup.upgrade()
        assert {column["name"] for column in inspect(connection).get_columns("activity_splits")} == {
            "activity_id", "status", "laps"
        }
        assert inspect(connection).get_indexes("activity_splits") == []
        assert connection.execute(text("SELECT activity_id, laps FROM activity_splits ORDER BY activity_id")).all() == before
        assert connection.execute(text("SELECT status FROM activity_splits ORDER BY activity_id")).scalars().all() == [
            "ready", "unavailable", "ready", "unavailable"
        ]
        status = next(column for column in inspect(connection).get_columns("activity_splits") if column["name"] == "status")
        assert "unavailable" in status["default"]
        cleanup.downgrade()
        assert connection.execute(text("SELECT activity_id, laps FROM activity_splits ORDER BY activity_id")).all() == before
        cleanup.upgrade()
        connection.execute(text("DROP SCHEMA pytest_splits_migration CASCADE"))
