import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, text
from sqlalchemy.orm import Session, sessionmaker

import app.main as main_module
from app.api.dependencies import get_db_session
from app.core.config import Settings
from app.infrastructure.db import models  # noqa: F401
from app.infrastructure.db.base import Base
from app.main import app

TEST_SCHEMA = os.environ.get("TEST_DATABASE_SCHEMA", "pytest_backend")
TEST_ENGINE = create_engine(
    Settings().database_url,
    connect_args={"options": f"-csearch_path={TEST_SCHEMA}"},
    future=True,
)
TestSessionLocal = sessionmaker(bind=TEST_ENGINE, autoflush=False, autocommit=False, expire_on_commit=False)


def _clear_test_tables(session: Session) -> None:
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(delete(table))
    session.commit()


@pytest.fixture(scope="session")
def prepare_test_database() -> Generator[None, None, None]:
    main_module.upgrade_database = lambda: None
    with TEST_ENGINE.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{TEST_SCHEMA}"'))
        connection.execute(text(f'SET search_path TO "{TEST_SCHEMA}"'))
        Base.metadata.drop_all(bind=connection)
        Base.metadata.create_all(bind=connection)
    session = TestSessionLocal()
    try:
        _clear_test_tables(session)
    finally:
        session.close()
    yield
    session = TestSessionLocal()
    try:
        _clear_test_tables(session)
    finally:
        session.close()


@pytest.fixture
def db_session(prepare_test_database) -> Generator[Session, None, None]:
    session = TestSessionLocal()
    try:
        _clear_test_tables(session)
        yield session
    finally:
        _clear_test_tables(session)
        session.close()


@pytest.fixture(autouse=True)
def override_test_dependencies(prepare_test_database) -> Generator[None, None, None]:
    def _get_test_db_session() -> Generator[Session, None, None]:
        session = TestSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides.clear()
    app.dependency_overrides[get_db_session] = _get_test_db_session
    try:
        yield
    finally:
        app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def client(prepare_test_database) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client
