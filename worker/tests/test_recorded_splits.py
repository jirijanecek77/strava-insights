from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

from app.garmin_client import GarminApiClient, GarminAuthenticationError, GarminSession
from app.models import Activity, ActivitySplits, ActivityStream
from app.services.recorded_splits import normalize_recorded_splits
from app.services.sync_import import FullImportService, IncrementalSyncService


def lap(index=1, distance=1000, **kwargs):
    return {
        "lapIndex": index,
        "distance": distance,
        "duration": 300,
        "averageSpeed": 10 / 3,
        "averageHR": 145,
        **kwargs,
    }


@pytest.mark.parametrize(
    "gain,loss,expected",
    [
        (12.5, 8.25, (12.5, 8.25)),
        (0, 0, (0, 0)),
        (None, None, (None, None)),
        (-1, float("inf"), (None, None)),
        (True, "12", (None, None)),
        (float("nan"), 3, (None, 3)),
    ],
)
def test_lap_elevation_retains_only_valid_garmin_totals(gain, loss, expected):
    result = normalize_recorded_splits(
        {"lapDTOs": [lap(elevationGain=gain, elevationLoss=loss)]}
    )[0]
    assert (
               result["elevation_gain_meters"],
               result["elevation_loss_meters"],
           ) == expected


def test_laps_preserve_interval_order_short_tail_and_timer_averages():
    result = normalize_recorded_splits(
        {
            "lapDTOs": [
                lap(3, 10, duration=5, averageSpeed=None, averageHR=None),
                lap(
                    1,
                    890.58,
                    intensityType="WARMUP",
                    movingDuration=250,
                    elapsedDuration=360,
                    averageMovingSpeed=4,
                ),
                lap(2, 400, intensityType="INTERVAL", duration=100, averageSpeed=4),
                lap(4, 0, duration=60, averageSpeed=0, averageHR=120),
            ]
        }
    )
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
    result = normalize_recorded_splits(
        {
            "lapDTOs": [
                lap(averageSpeed=float("inf"), duration=None, averageHR=float("nan"))
            ]
        }
    )
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
            return {"lapDTOs": [lap(elevationGain=12.5, elevationLoss=0)]}

    recorded = GarminApiClient().get_activity_splits(GarminSession(Client()), 123)[0]
    assert recorded["number"] == 1
    assert recorded["elevation_gain_meters"] == 12.5
    assert recorded["elevation_loss_meters"] == 0

    class Unauthorized:
        def get_activity_splits(self, _id):
            raise RuntimeError("API error 401")

    with pytest.raises(GarminAuthenticationError):
        GarminApiClient().get_activity_splits(GarminSession(Unauthorized()), 123)


class Api:
    def __init__(self, response=None, error=None):
        self.response = (
            response
            if response is not None
            else normalize_recorded_splits({"lapDTOs": [lap()]})
        )
        self.error = error
        self.calls = []
        self.garmin_session = SimpleNamespace(token_json=lambda: "refreshed")
        self.activities = [
            {
                "id": 1001,
                "name": "New activity",
                "type": "Run",
                "start_date": "2026-01-01T10:00:00Z",
                "distance": 1000,
                "moving_time": 300,
            }
        ]

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


def importer(api, monkeypatch, service_type=IncrementalSyncService):
    from app.services import sync_import

    session = Mock(spec=Session)
    planning = Mock(spec=sync_import.PlanningRepository)
    monkeypatch.setattr(sync_import, "PlanningRepository", Mock(return_value=planning))
    monkeypatch.setattr(sync_import, "UserCacheInvalidator", Mock())
    service = service_type(
        session,
        garmin_client=api,
        token_cipher=SimpleNamespace(
            decrypt=lambda value: value, encrypt=lambda value: value
        ),
    )
    for name in (
            "activities",
            "activity_streams",
            "sync_jobs",
            "checkpoints",
            "coaching",
    ):
        setattr(service, name, Mock(spec=type(getattr(service, name))))
    service.sync_jobs.get.return_value = SimpleNamespace(id=1, metadata_json={})
    service.activities.list_existing_source_activity_ids_for_user.return_value = set()
    service.activities.get_by_source_activity_id.return_value = None

    def save(activity):
        activity.id = 1
        return activity

    service.activities.save.side_effect = save
    service.activity_streams.get_by_activity_id.return_value = None
    service.activity_streams.save.side_effect = lambda stream: stream
    service.checkpoints.get_for_user.return_value = None
    service._get_garmin_credentials = Mock(return_value="token")
    service._persist_garmin_credentials = Mock()
    service._update_derived_data = Mock(return_value=(False, True))
    return service, session, planning


def run(service):
    return service._run(sync_job_id=1, user_id=1, after=None)


def saved_splits(session):
    return [
        call.args[0]
        for call in session.add.call_args_list
        if isinstance(call.args[0], ActivitySplits)
    ]


@pytest.mark.parametrize("service_type", [IncrementalSyncService, FullImportService])
@pytest.mark.parametrize("sport", ["Run", "Ride", "EBikeRide"])
def test_new_activity_fetches_once_in_existing_session_before_coaching(
        monkeypatch, service_type, sport
):
    api = Api()
    api.activities[0]["type"] = sport
    service, session, planning = importer(api, monkeypatch, service_type)

    def check_splits_before_coaching(**kwargs):
        assert saved_splits(session)[0].laps == api.response

    service.coaching.enqueue_activity_note.side_effect = check_splits_before_coaching
    assert run(service) == 1
    assert api.calls == [1001]
    assert saved_splits(session)[0].status == "ready"
    assert service.coaching.enqueue_activity_note.call_count == int(
        service.creates_coaching_notes
    )
    planning.enqueue.assert_called_once_with(
        user_id=1, sync_job_id=1, timezone="Europe/Prague"
    )
    service.activities.list_existing_source_activity_ids_for_user.return_value = {1001}
    service.activities.get_by_source_activity_id.return_value = (
        service.activities.save.call_args.args[0]
    )
    service.activity_streams.get_by_activity_id.return_value = (
        service.activity_streams.save.call_args.args[0]
    )
    assert run(service) == 0 and api.calls == [1001]


@pytest.mark.parametrize("source", ["scheduled", "manual_refresh", "full_recompute"])
@pytest.mark.parametrize("stream_backfill", [False, True])
def test_existing_activities_never_fetch_splits(monkeypatch, source, stream_backfill):
    api = Api()
    service, session, planning = importer(api, monkeypatch)
    activity = Activity(
        id=1,
        source_activity_id=1001,
        name="Custom name",
        source_provider="garmin",
        sport_type="Run",
    )
    service.activities.list_existing_source_activity_ids_for_user.return_value = {1001}
    service.activities.get_by_source_activity_id.return_value = activity
    service.activity_streams.get_by_activity_id.return_value = (
        None if stream_backfill else ActivityStream(time_stream={"data": [0, 60]})
    )
    service.sync_jobs.get.return_value.metadata_json = {"source": source}
    assert run(service) == int(stream_backfill)
    assert api.calls == [] and activity.name == "Custom name"
    session.add.assert_not_called()
    service.coaching.enqueue_activity_note.assert_not_called()
    planning.enqueue.assert_not_called()


@pytest.mark.parametrize(
    "error",
    [
        None,
        RuntimeError("HTTP 404"),
        RuntimeError("HTTP 429"),
        RuntimeError("HTTP 503"),
    ],
)
def test_optional_split_failure_does_not_block_activity_or_coaching(monkeypatch, error):
    api = Api(response=[], error=error)
    service, session, _ = importer(api, monkeypatch)
    assert run(service) == 1
    assert (
            saved_splits(session)[0].status == "unavailable"
            and saved_splits(session)[0].laps == []
    )
    service.coaching.enqueue_activity_note.assert_called_once_with(
        user_id=1, activity_id=1
    )
    service.activities.save.assert_called_once()


def test_auth_failure_leaves_new_activity_uninserted_for_reconnect(monkeypatch):
    api = Api(error=GarminAuthenticationError("Reconnect"))
    service, session, planning = importer(api, monkeypatch)
    with pytest.raises(GarminAuthenticationError):
        run(service)
    service.activities.save.assert_not_called()
    session.add.assert_not_called()
    service.coaching.enqueue_activity_note.assert_not_called()
    planning.enqueue.assert_not_called()
    api.error = None
    assert run(service) == 1
    assert saved_splits(session)[0].status == "ready"


def test_no_separate_split_task_or_schedule():
    from app.celery_app import celery_app

    assert "app.tasks.splits" not in celery_app.conf.include
    assert all(
        "splits" not in entry["task"]
        for entry in celery_app.conf.beat_schedule.values()
    )
