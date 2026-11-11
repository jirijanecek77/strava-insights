from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, delete, text
from sqlalchemy.orm import Session

from app.config import settings
from app.garmin_client import GarminApiClient, GarminAuthenticationError, GarminSession
from app.models import Activity, ActivityCoachingNote, ActivitySplits, ActivityStream, Base, GarminCredential, SyncJob, User
from app.services.recorded_splits import normalize_recorded_splits
from app.services.sync_import import FullImportService, IncrementalSyncService


def lap(index=1, distance=1000, **kwargs):
    return {"lapIndex": index, "distance": distance, "duration": 300, "averageSpeed": 10 / 3,
            "averageHR": 145, **kwargs}


def test_laps_preserve_interval_order_short_tail_and_timer_averages():
    result = normalize_recorded_splits({"lapDTOs": [
        lap(3, 10, duration=5, averageSpeed=None, averageHR=None),
        lap(1, 890.58, intensityType="WARMUP", movingDuration=250, elapsedDuration=360, averageMovingSpeed=4),
        lap(2, 400, intensityType="INTERVAL", duration=100, averageSpeed=4),
        lap(4, 0, duration=60, averageSpeed=0, averageHR=120),
    ]})
    assert [row["distance_meters"] for row in result] == [890.58, 400, 10, 0]
    assert result[1]["start_distance_meters"] == 890.58
    assert result[2]["end_distance_meters"] == 1300.58
    assert result[0]["average_pace_seconds_per_km"] == 300
    assert result[0]["duration_seconds"] == 300
    assert result[0]["elapsed_duration_seconds"] == 360
    assert result[1]["average_speed_kph"] == 14.4
    assert result[2]["average_pace_seconds_per_km"] == 500
    assert result[2]["average_heartrate_bpm"] is None
    assert result[3]["average_speed_kph"] is None
    assert result[3]["average_heartrate_bpm"] == 120


def test_bad_metrics_are_gaps_and_unknown_distance_cannot_shift_following_laps():
    result = normalize_recorded_splits({"lapDTOs": [lap(averageSpeed=float("inf"), duration=None,
                                                          averageHR=float("nan"))]})
    assert result[0]["average_speed_kph"] is None
    assert result[0]["average_heartrate_bpm"] is None
    with pytest.raises(ValueError):
        normalize_recorded_splits({"lapDTOs": [lap(distance=None), lap(2)]})
    with pytest.raises(ValueError):
        normalize_recorded_splits({"splitSummaries": []})
    assert normalize_recorded_splits({"lapDTOs": []}) == []


def test_adapter_fetches_recorded_laps_and_maps_authentication():
    class Client:
        def get_activity_splits(self, activity_id):
            assert activity_id == "123"
            return {"lapDTOs": [lap()]}
    assert GarminApiClient().get_activity_splits(GarminSession(Client()), 123)[0]["number"] == 1
    class Unauthorized:
        def get_activity_splits(self, _id):
            raise RuntimeError("API error 401")
    with pytest.raises(GarminAuthenticationError):
        GarminApiClient().get_activity_splits(GarminSession(Unauthorized()), 123)


@pytest.fixture(scope="module")
def splits_engine():
    engine = create_engine(settings.database_url, connect_args={"options": "-csearch_path=pytest_inline_splits"})
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS pytest_inline_splits CASCADE"))
        conn.execute(text("CREATE SCHEMA pytest_inline_splits"))
        Base.metadata.create_all(conn)
    yield engine
    engine.dispose()


@pytest.fixture
def session(splits_engine, monkeypatch):
    monkeypatch.setattr("app.services.sync_import.UserCacheInvalidator",
                        lambda: SimpleNamespace(invalidate_user=lambda _: 0))
    # Derived analytics are outside split importing; the rest of the import uses real persistence.
    monkeypatch.setattr("app.services.sync_import.BaseImportService._update_derived_data",
                        lambda *args, **kwargs: (False, True))
    with Session(splits_engine, expire_on_commit=False) as db:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(delete(table))
        db.add(User(id=1, display_name="Athlete", is_active=True))
        db.add(GarminCredential(user_id=1, external_user_id="external", email_encrypted="email",
                               token_json_encrypted="token", connection_status="connected"))
        db.add(SyncJob(id=1, user_id=1, sync_type="incremental", status="running", metadata_json={}))
        db.commit()
        yield db
        db.rollback()
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(delete(table))
        db.commit()


class Api:
    def __init__(self, response=None, error=None):
        self.response = response if response is not None else normalize_recorded_splits({"lapDTOs": [lap()]})
        self.error = error
        self.calls = []
        self.garmin_session = SimpleNamespace(token_json=lambda: "refreshed")
        self.activities = [{"id": 1001, "name": "New activity", "type": "Run",
                            "start_date": "2026-01-01T10:00:00Z", "distance": 1000, "moving_time": 300}]

    def connect(self, _token):
        return self.garmin_session

    def get_activities(self, garmin_session, **kwargs):
        assert garmin_session is self.garmin_session
        return self.activities

    def get_activity_splits(self, garmin_session, activity_id):
        assert garmin_session is self.garmin_session
        self.calls.append(activity_id)
        if self.error:
            raise self.error
        return self.response

    def get_activity_stream(self, garmin_session, activity_id):
        assert garmin_session is self.garmin_session
        return {"time": {"data": [0, 300]}, "distance": {"data": [0, 1000]}}


def importer(session, api, service_type=IncrementalSyncService):
    return service_type(session, garmin_client=api,
                        token_cipher=SimpleNamespace(decrypt=lambda value: value, encrypt=lambda value: value))


def run(service):
    return service._run(sync_job_id=1, user_id=1, after=None)


@pytest.mark.parametrize("service_type", [IncrementalSyncService, FullImportService])
def test_new_activity_fetches_once_in_existing_session_before_coaching(session, service_type):
    api = Api()
    service = importer(session, api, service_type)
    enqueue = service.coaching.enqueue_activity_note

    def check_splits_before_coaching(**kwargs):
        row = session.get(ActivitySplits, kwargs["activity_id"])
        assert row.status == "ready" and row.laps == api.response
        return enqueue(**kwargs)

    service.coaching.enqueue_activity_note = check_splits_before_coaching
    assert run(service) == 1
    assert api.calls == [1001]
    assert session.query(ActivitySplits).one().laps == api.response
    assert session.query(ActivityCoachingNote).count() == int(service.creates_coaching_notes)
    assert run(service) == 0
    assert api.calls == [1001]


@pytest.mark.parametrize("source", ["scheduled", "manual_refresh", "full_recompute"])
@pytest.mark.parametrize("stream_backfill", [False, True])
def test_existing_activities_never_fetch_splits(session, source, stream_backfill):
    api = Api()
    service = importer(session, api)
    run(service)
    activity = session.query(Activity).one()
    activity.name = "Custom name"
    stored_laps = session.get(ActivitySplits, activity.id).laps
    # Include existing activities without split rows as well as those already populated.
    if source == "full_recompute":
        session.delete(session.get(ActivitySplits, activity.id))
    if stream_backfill:
        session.query(ActivityStream).delete()
    session.get(SyncJob, 1).metadata_json = {"source": source}
    session.commit()
    api.calls.clear()
    assert run(service) == int(stream_backfill)
    assert api.calls == []
    assert activity.name == "Custom name"
    row = session.get(ActivitySplits, activity.id)
    if source == "full_recompute":
        assert row is None
    else:
        assert row.laps == stored_laps
    assert session.query(ActivityCoachingNote).count() == 1


@pytest.mark.parametrize("error", [None, RuntimeError("HTTP 404"), RuntimeError("HTTP 429"), RuntimeError("HTTP 503")])
def test_optional_split_failure_does_not_block_activity_or_coaching(session, error):
    api = Api(response=[], error=error)
    service = importer(session, api)
    assert run(service) == 1
    assert session.query(ActivitySplits).one().status == "unavailable"
    assert session.query(ActivitySplits).one().laps == []
    assert session.query(ActivityCoachingNote).count() == 1
    assert run(service) == 0
    assert api.calls == [1001]


def test_auth_failure_leaves_new_activity_uninserted_for_reconnect(session):
    api = Api(error=GarminAuthenticationError("Reconnect"))
    service = importer(session, api)
    with pytest.raises(GarminAuthenticationError):
        run(service)
    session.rollback()
    assert session.query(Activity).count() == 0
    assert session.query(ActivitySplits).count() == 0
    assert session.query(ActivityCoachingNote).count() == 0
    api.error = None
    assert run(service) == 1
    assert session.query(ActivitySplits).one().status == "ready"


def test_no_separate_split_task_or_schedule():
    from app.celery_app import celery_app
    assert "app.tasks.splits" not in celery_app.conf.include
    assert all("splits" not in entry["task"] for entry in celery_app.conf.beat_schedule.values())
