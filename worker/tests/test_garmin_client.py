from app.garmin_client import GarminApiClient
from app.services.sync_import import BaseImportService
from typing import Any, cast


def test_normalize_summary_omits_non_run_and_non_ride_activities() -> None:
    normalized = GarminApiClient.normalize_summary(
        {
            "activityId": 123,
            "activityName": "Strength training",
            "activityType": {"typeKey": "strength_training"},
            "startTimeGMT": "2026-08-26T10:00:00Z",
        }
    )

    assert normalized["type"] is None

    for type_key in ("swimming", "walking", "yoga", "cardio_training"):
        assert GarminApiClient.normalize_summary(
            {"activityId": 124, "activityType": {"typeKey": type_key}}
        )["type"] is None


def test_normalize_summary_accepts_all_run_and_ride_variants() -> None:
    for type_key in ("running", "trail_running", "treadmill_running"):
        assert GarminApiClient.normalize_summary(
            {"activityId": 125, "activityType": {"typeKey": type_key}}
        )["type"] == "Run"
    for type_key in ("cycling", "indoor_cycling", "mountain_biking"):
        assert GarminApiClient.normalize_summary(
            {"activityId": 126, "activityType": {"typeKey": type_key}}
        )["type"] == "Ride"


def test_normalize_summary_prefers_moving_duration_over_elapsed_duration() -> None:
    normalized = GarminApiClient.normalize_summary(
        {
            "activityId": 127,
            "activityType": {"typeKey": "running"},
            "distance": 10000,
            "duration": 4200,
            "movingDuration": 3600,
            "elapsedDuration": 4200,
            "averageSpeed": 2.0,
            "averageMovingSpeed": 2.75,
        }
    )

    assert normalized["moving_time"] == 3600
    assert normalized["elapsed_time"] == 4200
    assert normalized["average_speed"] == 2.75


def test_normalize_stream_maps_garmin_detail_descriptor_keys() -> None:
    samples = [
        {
            "sumDuration": 0,
            "sumDistance": 0,
            "directLatitude": 50.0,
            "directLongitude": 14.0,
            "directElevation": 220.0,
            "directHeartRate": 140,
            "directSpeed": 3.0,
        },
        {
            "sumDuration": 1,
            "sumDistance": 3,
            "directLatitude": 50.0001,
            "directLongitude": 14.0001,
            "directElevation": 220.5,
            "directHeartRate": 141,
            "directSpeed": 3.1,
        },
    ]

    normalized = GarminApiClient.normalize_stream(samples)

    assert normalized["time"]["data"] == [0, 1]
    assert normalized["distance"]["data"] == [0, 3]
    assert normalized["latlng"]["data"] == [[50.0, 14.0], [50.0001, 14.0001]]
    assert normalized["altitude"]["data"] == [220.0, 220.5]
    assert normalized["heartrate"]["data"] == [140, 141]
    assert normalized["velocity_smooth"]["data"] == [3.0, 3.1]


def test_existing_activity_with_empty_stream_is_selected_for_backfill() -> None:
    class ActivityRepositoryStub:
        def get_by_source_activity_id(self, user_id: int, source_activity_id: int):
            return type("Activity", (), {"id": 7})()

    class ActivityStreamRepositoryStub:
        def get_by_activity_id(self, activity_id: int):
            return type(
                "ActivityStream",
                (),
                {
                    "time_stream": {},
                    "distance_stream": {},
                    "latlng_stream": {},
                    "altitude_stream": {},
                    "velocity_smooth_stream": {},
                    "heartrate_stream": {},
                },
            )()

    service = cast(Any, BaseImportService.__new__(BaseImportService))
    service.activities = ActivityRepositoryStub()
    service.activity_streams = ActivityStreamRepositoryStub()

    assert service._existing_activity_needs_stream_backfill(
        user_id=1, source_activity_id=123
    )


def _upsert_existing_activity(existing):
    class ActivityRepositoryStub:
        def get_by_source_activity_id(self, user_id: int, source_activity_id: int):
            return existing

        def save(self, activity):
            return activity

    service = cast(Any, BaseImportService.__new__(BaseImportService))
    service.activities = ActivityRepositoryStub()
    return service._upsert_activity(
        user_id=1,
        payload={
            "id": 123,
            "name": "Garmin Name",
            "type": "Run",
            "start_date": "2026-09-01T06:00:00Z",
            "distance": 10000,
            "moving_time": 2700,
        },
    )


def test_reimport_keeps_existing_activity_name() -> None:
    from app.models import Activity

    renamed = Activity(user_id=1, source_activity_id=123, name="My Name")
    reimported = _upsert_existing_activity(renamed)
    assert reimported.name == "My Name"
    assert reimported.moving_time_seconds == 2700


def test_first_import_uses_garmin_name() -> None:
    assert _upsert_existing_activity(None).name == "Garmin Name"
