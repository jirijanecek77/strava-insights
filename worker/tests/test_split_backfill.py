from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock, create_autospec

import pytest
from sqlalchemy.orm import Session

from app.garmin_client import GarminAuthenticationError
from app.models import Activity, ActivitySplits, GarminCredential, User
from app.services.split_backfill import (
    SplitBackfillError,
    SplitBackfillService,
    SplitBackfillStore,
    SplitBackfillTarget,
    SplitBackfillValidationError,
)
from app.split_backfill_repository import SplitBackfillRepository


def lap(**kwargs):
    return {
        "number": 1,
        "start_distance_meters": 0,
        "end_distance_meters": 1000,
        "distance_meters": 1000,
        "average_heartrate_bpm": 145,
        "elevation_gain_meters": 12.5,
        "elevation_loss_meters": 0,
        **kwargs,
    }


class GarminStub:
    def __init__(self):
        self.calls = []
        self.responses = {}
        self.garmin_session = SimpleNamespace(token_json=lambda: "refreshed-token")

    def connect(self, token):
        assert token.startswith("encrypted:") is False
        return self.garmin_session

    def get_activity_splits(self, session, source_id):
        assert session is self.garmin_session
        self.calls.append(source_id)
        response = self.responses.get(source_id, [lap()])
        if isinstance(response, Exception):
            raise response
        return deepcopy(response)


@dataclass
class BackfillState:
    activities: dict[int, Activity]
    splits: dict[int, ActivitySplits]
    credential: GarminCredential
    repository: Mock
    session: Mock
    active_sync: bool = False


@pytest.fixture
def db():
    activities = {
        activity_id: Activity(
            id=activity_id,
            user_id=user,
            source_provider=provider,
            source_activity_id=1000 + activity_id,
            name="Original name",
            sport_type="Run",
        )
        for activity_id, user, provider in (
            (10, 1, "garmin"),
            (20, 1, "legacy"),
            (30, 1, "garmin"),
            (40, 2, "garmin"),
        )
    }
    state = BackfillState(
        activities,
        {
            10: ActivitySplits(
                activity_id=10,
                status="ready",
                laps=[
                    lap(
                        elevation_gain_meters=None,
                        elevation_loss_meters=None,
                        average_heartrate_bpm=155,
                    )
                ],
            )
        },
        GarminCredential(
            user_id=1,
            connection_status="connected",
            token_json_encrypted="encrypted:token",
        ),
        create_autospec(SplitBackfillStore, instance=True),
        Mock(spec=Session),
    )
    user = User(id=1, is_active=True)
    state.session.get.side_effect = lambda model, key: {
        Activity: state.activities,
        ActivitySplits: state.splits,
        User: {1: user},
    }[model].get(key)
    state.session.scalar.return_value = state.credential
    state.session.add.side_effect = lambda row: state.splits.__setitem__(
        row.activity_id, row
    )
    adapter = SplitBackfillRepository(state.session)

    def ensure_idle(user_id):
        if state.active_sync:
            raise SplitBackfillValidationError(
                "Finish the athlete's active sync first."
            )

    adapter._ensure_idle = Mock(side_effect=ensure_idle)
    state.repository.get_token.side_effect = adapter.get_token
    state.repository.list_batch.side_effect = lambda user_id, after_id, batch_size: [
        SplitBackfillTarget(row.id, row.source_activity_id)
        for row in state.activities.values()
        if row.user_id == user_id
           and row.source_provider == "garmin"
           and row.id > after_id
    ][:batch_size]
    state.repository.save_token.side_effect = adapter.save_token
    state.repository.save_laps.side_effect = adapter.save_laps
    state.repository.require_reauthentication.side_effect = (
        adapter.require_reauthentication
    )
    state.repository.rollback.side_effect = adapter.rollback
    return state


def service(db, api=None):
    invalidated, pauses, progress = [], [], []
    cipher = SimpleNamespace(
        decrypt=lambda token: token.removeprefix("encrypted:"),
        encrypt=lambda token: "encrypted:" + token,
    )
    result = SplitBackfillService(
        db.repository,
        api or GarminStub(),
        cipher,
        SimpleNamespace(invalidate_user=invalidated.append),
        sleep=pauses.append,
        on_progress=progress.append,
    )
    return result, invalidated, pauses, progress


def test_backfill_persists_elevation_across_batches_without_changing_other_metrics(db):
    api = GarminStub()
    runner, invalidated, pauses, progress = service(db, api)
    result = runner.run(user_id=1, batch_size=1, delay_seconds=1)
    assert api.calls == [1010, 1030]
    assert result.processed == 2 and result.after_id == 30 and result.updated == 2
    first = db.splits.get(10)
    assert first.laps[0]["elevation_gain_meters"] == 12.5
    assert first.laps[0]["elevation_loss_meters"] == 0
    assert first.laps[0]["average_heartrate_bpm"] == 155
    assert db.splits.get(30).status == "ready"
    assert db.splits.get(20) is None and db.splits.get(40) is None
    assert db.activities[10].name == "Original name"
    assert db.credential.token_json_encrypted == "encrypted:refreshed-token"
    assert invalidated == [1, 1] and pauses == [1]
    assert [row.after_id for row in progress] == [10, 30]
    second = runner.run(user_id=1, delay_seconds=0)
    assert second.updated == 0


def test_failure_retains_previous_laps_and_reports_the_last_committed_cursor(db):
    api = GarminStub()
    api.responses[1030] = ValueError("Invalid Garmin lap payload")
    runner, _, _, _ = service(db, api)
    with pytest.raises(SplitBackfillError) as caught:
        runner.run(user_id=1, delay_seconds=0)
    assert caught.value.after_id == 10 and caught.value.activity_id == 30
    assert db.splits.get(30) is None
    assert db.splits.get(10).laps[0]["elevation_gain_meters"] == 12.5
    api.responses.clear()
    runner.run(user_id=1, after_id=caught.value.after_id, delay_seconds=0)
    assert api.calls == [1010, 1030, 1030]


@pytest.mark.parametrize(
    "response", [[], [lap(end_distance_meters=999)], [lap(), lap(number=2)]]
)
def test_empty_or_changed_lap_boundaries_cannot_replace_recorded_data(db, response):
    api = GarminStub()
    api.responses[1010] = response
    original = deepcopy(db.splits.get(10).laps)
    runner, _, _, _ = service(db, api)
    with pytest.raises(SplitBackfillError) as caught:
        runner.run(user_id=1, delay_seconds=0)
    assert caught.value.after_id == 0
    assert db.splits.get(10).laps == original


def test_auth_failure_marks_reconnect_without_changing_splits(db):
    api = GarminStub()
    api.responses[1010] = GarminAuthenticationError("Reconnect")
    runner, _, _, _ = service(db, api)
    with pytest.raises(SplitBackfillError):
        runner.run(user_id=1, delay_seconds=0)
    credential = db.credential
    assert credential.connection_status == "reauthentication_required"
    assert db.splits.get(10).laps[0]["elevation_gain_meters"] is None


def test_transient_network_errors_retry_without_advancing_progress(db):
    import requests

    api = GarminStub()
    original = api.get_activity_splits
    failures = [requests.ConnectionError("temporary")]

    def fetch(session, source_id):
        if failures:
            raise failures.pop()
        return original(session, source_id)

    api.get_activity_splits = fetch
    runner, _, pauses, _ = service(db, api)
    assert runner.run(user_id=1, delay_seconds=0).processed == 2
    assert pauses == [2]


def test_exhausted_retries_do_not_erase_data_or_advance_cursor(db):
    import requests

    api = GarminStub()
    token = ["initial-token"]
    api.garmin_session.token_json = lambda: token[0]
    api.responses[1010] = requests.ConnectionError("temporary")
    original = api.get_activity_splits

    def fetch(session, source_id):
        token[0] = "rotated-on-failed-request"
        return original(session, source_id)

    api.get_activity_splits = fetch
    runner, _, pauses, _ = service(db, api)
    with pytest.raises(SplitBackfillError) as caught:
        runner.run(user_id=1, delay_seconds=0)
    assert caught.value.after_id == 0
    assert api.calls == [1010] * 3 and pauses == [2, 4]
    assert db.credential.token_json_encrypted == "encrypted:rotated-on-failed-request"


def test_refuses_active_sync_before_any_provider_call(db):
    db.active_sync = True
    api = GarminStub()
    runner, _, _, _ = service(db, api)
    with pytest.raises(SplitBackfillError):
        runner.run(user_id=1)
    assert api.calls == []


def test_empty_response_for_missing_splits_is_recorded_as_unavailable(db):
    api = GarminStub()
    api.responses[1030] = []
    runner, _, _, _ = service(db, api)
    runner.run(user_id=1, after_id=10, delay_seconds=0)
    assert db.splits.get(30).status == "unavailable"
    assert db.splits.get(30).laps == []


def test_provider_omission_does_not_erase_already_recorded_totals(db):
    db.splits.get(10).laps = [lap()]
    api = GarminStub()
    api.responses[1010] = [lap(elevation_gain_meters=None, elevation_loss_meters=None)]
    runner, _, _, _ = service(db, api)
    runner.run(user_id=1, delay_seconds=0)
    assert db.splits.get(10).laps[0]["elevation_gain_meters"] == 12.5
    assert db.splits.get(10).laps[0]["elevation_loss_meters"] == 0


@pytest.mark.parametrize(
    "retry_after,attempts,delays", [("3", 3, [3, 4]), ("600", 1, [])]
)
def test_provider_retry_after_is_respected(db, retry_after, attempts, delays):
    import requests

    response = requests.Response()
    response.status_code = 429
    response.headers["Retry-After"] = retry_after
    api = GarminStub()
    api.responses[1010] = requests.HTTPError(response=response)
    runner, _, pauses, _ = service(db, api)
    with pytest.raises(SplitBackfillError) as caught:
        runner.run(user_id=1, delay_seconds=0)
    assert caught.value.after_id == 0
    assert api.calls == [1010] * attempts and pauses == delays


@pytest.mark.parametrize(
    "kwargs",
    [
        {"batch_size": 0},
        {"batch_size": 1001},
        {"after_id": -1},
        {"delay_seconds": -1},
        {"delay_seconds": float("nan")},
    ],
)
def test_invalid_options_never_contact_garmin(db, kwargs):
    api = GarminStub()
    runner, _, _, _ = service(db, api)
    with pytest.raises(ValueError):
        runner.run(user_id=1, **kwargs)
    assert api.calls == []


def test_repository_rejects_a_target_owned_by_another_athlete(db):
    repository = SplitBackfillRepository(db.session)
    with pytest.raises(SplitBackfillValidationError, match="does not belong"):
        repository.save_laps(1, SplitBackfillTarget(40, 1040), [lap()], "new-token")
    db.session.commit.assert_not_called()
    db.session.add.assert_not_called()


def test_repository_refuses_an_active_sync_with_mocked_query():
    session = Mock(spec=Session)
    session.get.return_value = User(id=1, is_active=True)
    session.scalar.return_value = 99
    with pytest.raises(SplitBackfillValidationError, match="active sync"):
        SplitBackfillRepository(session).get_token(1)
    session.commit.assert_not_called()
