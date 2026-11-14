from collections.abc import Generator
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.main as main_module
from app.api.dependencies import get_db_session
from app.main import app


@pytest.fixture(scope="session")
def patch_app_startup():
    original = main_module.upgrade_database
    main_module.upgrade_database = lambda: None
    yield
    main_module.upgrade_database = original


@pytest.fixture
def db_session() -> Mock:
    session = Mock(spec=Session)
    session.query.side_effect = AssertionError("Mock the repository used by this test.")
    session.execute.side_effect = AssertionError(
        "Mock the repository used by this test."
    )
    session.connection.side_effect = AssertionError(
        "Tests must not open a database connection."
    )
    return session


@pytest.fixture(autouse=True)
def override_test_dependencies(db_session):
    def mocked_session():
        yield db_session

    app.dependency_overrides.clear()
    app.dependency_overrides[get_db_session] = mocked_session
    yield
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def client(patch_app_startup) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client
