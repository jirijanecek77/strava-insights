from app.application.auth.current_user import CurrentUserService
from app.infrastructure.db.models.activity_splits import ActivitySplits
from app.infrastructure.db.models.activity import Activity
from app.main import app
from tests.test_activity_rename import _seed
from tests.test_read_endpoint_integration import CurrentUserServiceStub


def test_detail_reads_recorded_laps_locally_and_enforces_ownership(client, db_session):
    _seed(db_session)
    db_session.add(ActivitySplits(activity_id=11, status="ready", laps=[{
        "number": 1, "lap_type": "INTERVAL", "distance_meters": 400,
        "start_distance_meters": 0, "end_distance_meters": 400, "duration_seconds": 100,
        "average_pace_seconds_per_km": 250, "average_speed_kph": 14.4, "average_heartrate_bpm": None,
    }]))
    db_session.commit()
    app.dependency_overrides[CurrentUserService] = lambda: CurrentUserServiceStub(1)
    result = client.get("/activities/11")
    assert result.status_code == 200
    assert result.json()["splits"]["status"] == "ready"
    assert result.json()["splits"]["laps"][0]["distance_meters"] == 400
    assert result.json()["splits"]["laps"][0]["average_heartrate_bpm"] is None
    assert client.get("/activities/12").status_code == 404


def test_existing_activity_without_splits_is_readable(client, db_session):
    _seed(db_session)
    app.dependency_overrides[CurrentUserService] = lambda: CurrentUserServiceStub(1)
    result = client.get("/activities/11")
    assert result.status_code == 200
    assert result.json()["splits"] == {"status": "unavailable", "laps": []}


def test_legacy_activity_does_not_offer_an_impossible_garmin_backfill(client, db_session):
    _seed(db_session)
    db_session.get(Activity, 11).source_provider = "legacy"
    db_session.add(ActivitySplits(activity_id=11, status="ready", laps=[]))
    db_session.commit()
    app.dependency_overrides[CurrentUserService] = lambda: CurrentUserServiceStub(1)
    assert client.get("/activities/11").json()["splits"] == {"status": "unavailable", "laps": []}
