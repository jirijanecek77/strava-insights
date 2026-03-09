import time

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError

from app.infrastructure.db.session import engine


def upgrade_database() -> None:
    alembic_config = Config("alembic.ini")
    for attempt in range(10):
        try:
            inspector = inspect(engine)
            table_names = set(inspector.get_table_names())
            if "users" in table_names and "alembic_version" not in table_names:
                command.stamp(alembic_config, "head")
                return
            command.upgrade(alembic_config, "head")
            return
        except OperationalError:
            if attempt == 9:
                raise
            time.sleep(1)
