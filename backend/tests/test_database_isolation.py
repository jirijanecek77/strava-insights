from unittest.mock import Mock

import pytest


def test_api_database_dependency_is_only_a_mock(db_session):
    assert isinstance(db_session, Mock)
    with pytest.raises(AssertionError, match="must not open"):
        db_session.connection()
