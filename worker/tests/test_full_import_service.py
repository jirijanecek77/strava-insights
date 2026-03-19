import logging
from datetime import UTC, datetime, timedelta

from app.services.sync_import import FullImportService, IncrementalSyncService
from app.strava_client import StravaActivityStreamNotFoundError


class SyncJobStub:
    def __init__(self) -> None:
        self.id = 1
        self.user_id = 1
        self.status = "queued"
        self.sync_type = "full_import"
        self.progress_total = None
        self.progress_completed = None
        self.metadata_json = {}
        self.started_at = None
        self.finished_at = None
        self.error_message = None


class OAuthTokenStub:
    def __init__(self, access_token_encrypted: str, refresh_token_encrypted: str, expires_at: datetime) -> None:
        self.access_token_encrypted = access_token_encrypted
        self.refresh_token_encrypted = refresh_token_encrypted
        self.expires_at = expires_at
        self.scope = None


class ActivityStub:
    def __init__(self, activity_id: int | None = None) -> None:
        self.id = activity_id


class ActivityStreamStub:
    def __init__(self, activity_id: int) -> None:
        self.activity_id = activity_id


class SessionStub:
    def __init__(self) -> None:
        self.commits = 0
        self.flushes = 0

    def commit(self):
        self.commits += 1

    def flush(self):
        self.flushes += 1


class SyncJobRepositoryStub:
    def __init__(self, sync_job: SyncJobStub) -> None:
        self.sync_job = sync_job

    def get(self, _sync_job_id: int, _user_id: int):
        return self.sync_job

    def update_running(self, sync_job, *, progress_total):
        sync_job.status = "running"
        sync_job.progress_total = progress_total
        sync_job.progress_completed = 0

    def update_progress(self, sync_job, *, completed, total):
        sync_job.progress_completed = completed
        sync_job.progress_total = total

    def complete(self, sync_job, *, imported_activities):
        sync_job.status = "completed"
        sync_job.progress_completed = imported_activities
        sync_job.progress_total = imported_activities


class OAuthTokenRepositoryStub:
    def __init__(self, oauth_token) -> None:
        self.oauth_token = oauth_token

    def get_for_user(self, _user_id: int, provider: str = "strava"):
        return self.oauth_token


class ActivityRepositoryStub:
    def __init__(self) -> None:
        self.by_id = {}
        self.counter = 1
        self.latest_start_date_utc = None
        self.existing_strava_ids = set()

    def get_by_strava_id(self, _user_id: int, strava_activity_id: int):
        return self.by_id.get(strava_activity_id)

    def get_by_id(self, activity_id: int):
        return next((activity for activity in self.by_id.values() if activity.id == activity_id), None)

    def list_existing_strava_ids_for_user(self, _user_id: int, strava_activity_ids: list[int]):
        return {strava_activity_id for strava_activity_id in strava_activity_ids if strava_activity_id in self.existing_strava_ids}

    def save(self, activity):
        if getattr(activity, "id", None) is None:
            activity.id = self.counter
            self.counter += 1
        self.by_id[activity.strava_activity_id] = activity
        return activity

    def get_latest_start_date_utc_for_user(self, _user_id: int):
        return self.latest_start_date_utc


class ActivityStreamRepositoryStub:
    def __init__(self) -> None:
        self.by_activity_id = {}

    def get_by_activity_id(self, activity_id: int):
        return self.by_activity_id.get(activity_id)

    def save(self, activity_stream):
        self.by_activity_id[activity_stream.activity_id] = activity_stream
        return activity_stream


class CheckpointRepositoryStub:
    def __init__(self) -> None:
        self.value = None

    def get_for_user(self, _user_id: int, _sync_type: str):
        if self.value is None:
            return None
        return type("CheckpointStub", (), self.value)()

    def upsert(self, **kwargs):
        self.value = kwargs


class CacheInvalidatorStub:
    def __init__(self) -> None:
        self.user_ids: list[int] = []

    def invalidate_user(self, user_id: int) -> int:
        self.user_ids.append(user_id)
        return 1


class ReadModelBuilderStub:
    def __init__(self) -> None:
        self.user_ids: list[int] = []

    def rebuild_for_user(self, user_id: int) -> None:
        self.user_ids.append(user_id)


class TokenCipherStub:
    def encrypt(self, value: str) -> str:
        return f"enc:{value}"

    def decrypt(self, value: str) -> str:
        return value.replace("enc:", "", 1)


class StravaClientStub:
    def __init__(self) -> None:
        self.after = None
        self.stream_calls: list[int] = []

    def refresh_access_token(self, refresh_token: str):
        assert refresh_token == "refresh-token"
        return {
            "access_token": "fresh-access-token",
            "refresh_token": "fresh-refresh-token",
            "expires_at": int((datetime.now(UTC) + timedelta(hours=6)).timestamp()),
            "scope": "read,activity:read_all",
            "athlete": {"id": 162181, "firstname": "Jiri", "lastname": "Janecek", "profile": None},
        }

    def parse_expires_at(self, payload):
        return datetime.fromtimestamp(payload["expires_at"], tz=UTC)

    def get_activities(self, access_token: str, *, after=None):
        assert access_token in {"access-token", "fresh-access-token"}
        self.after = after
        return [
            {
                "id": 100,
                "name": "Morning Run",
                "type": "Run",
                "start_date": "2026-03-09T06:00:00Z",
                "start_date_local": "2026-03-09T07:00:00+01:00",
                "distance": 10000.0,
                "moving_time": 2700,
                "elapsed_time": 2800,
                "total_elevation_gain": 100.0,
                "elev_high": 300.0,
                "elev_low": 200.0,
                "average_speed": 3.7,
                "max_speed": 4.5,
                "average_heartrate": 150.0,
                "max_heartrate": 170,
                "average_cadence": 84.0,
                "start_latlng": [50.0, 14.0],
            }
        ]

    def get_activity_stream(self, access_token: str, activity_id: int):
        assert access_token in {"access-token", "fresh-access-token"}
        assert activity_id == 100
        self.stream_calls.append(activity_id)
        return {
            "time": {"data": [0, 60, 120, 180]},
            "distance": {"data": [0, 250, 750, 1250]},
            "latlng": {"data": [[50.0, 14.0], [50.1, 14.1]]},
            "altitude": {"data": [200, 201]},
            "velocity_smooth": {"data": [3.5, 3.6, 3.7, 3.8]},
            "heartrate": {"data": [145, 146, 150, 152]},
        }


class MissingStreamStravaClientStub(StravaClientStub):
    def get_activity_stream(self, access_token: str, activity_id: int):
        raise StravaActivityStreamNotFoundError(activity_id)


def test_full_import_service_imports_activities_updates_progress_and_checkpoint() -> None:
    session = SessionStub()
    sync_job = SyncJobStub()
    oauth_token = OAuthTokenStub("enc:access-token", "enc:refresh-token", datetime.now(UTC) + timedelta(hours=1))
    service = FullImportService(session, strava_client=StravaClientStub(), token_cipher=TokenCipherStub())
    service.sync_jobs = SyncJobRepositoryStub(sync_job)
    service.oauth_tokens = OAuthTokenRepositoryStub(oauth_token)
    service.activities = ActivityRepositoryStub()
    service.activity_streams = ActivityStreamRepositoryStub()
    service.checkpoints = CheckpointRepositoryStub()
    service.cache_invalidator = CacheInvalidatorStub()
    service.read_model_builder = ReadModelBuilderStub()

    imported_count = service.run(sync_job_id=1, user_id=1)

    assert imported_count == 1
    assert sync_job.status == "completed"
    assert sync_job.progress_completed == 1
    assert service.checkpoints.value["checkpoint_value"] == "2026-03-09T06:00:00+00:00"
    assert 100 in service.activities.by_id
    assert service.activities.by_id[100].distance_km == 10
    assert service.activities.by_id[100].moving_time_display == "45:00"
    assert service.activities.by_id[100].average_pace_display == "4:30"
    assert service.activities.by_id[100].summary_metric_display == "4:30 /km"
    assert service.activities.by_id[100].heart_rate_drift_bpm == 5
    assert service.activity_streams.by_activity_id[1].heartrate_stream == {"data": [145, 146, 150, 152]}
    assert service.read_model_builder.user_ids == [1]
    assert service.cache_invalidator.user_ids == [1]


def test_full_import_service_refreshes_expired_token_before_import() -> None:
    session = SessionStub()
    sync_job = SyncJobStub()
    oauth_token = OAuthTokenStub("enc:stale-access-token", "enc:refresh-token", datetime.now(UTC) - timedelta(minutes=5))
    service = FullImportService(session, strava_client=StravaClientStub(), token_cipher=TokenCipherStub())
    service.sync_jobs = SyncJobRepositoryStub(sync_job)
    service.oauth_tokens = OAuthTokenRepositoryStub(oauth_token)
    service.activities = ActivityRepositoryStub()
    service.activity_streams = ActivityStreamRepositoryStub()
    service.checkpoints = CheckpointRepositoryStub()
    service.cache_invalidator = CacheInvalidatorStub()
    service.read_model_builder = ReadModelBuilderStub()

    service.run(sync_job_id=1, user_id=1)

    assert oauth_token.access_token_encrypted == "enc:fresh-access-token"
    assert oauth_token.refresh_token_encrypted == "enc:fresh-refresh-token"


def test_full_import_service_logs_token_refresh(caplog) -> None:
    session = SessionStub()
    sync_job = SyncJobStub()
    oauth_token = OAuthTokenStub("enc:stale-access-token", "enc:refresh-token", datetime.now(UTC) - timedelta(minutes=5))
    service = FullImportService(session, strava_client=StravaClientStub(), token_cipher=TokenCipherStub())
    service.sync_jobs = SyncJobRepositoryStub(sync_job)
    service.oauth_tokens = OAuthTokenRepositoryStub(oauth_token)
    service.activities = ActivityRepositoryStub()
    service.activity_streams = ActivityStreamRepositoryStub()
    service.checkpoints = CheckpointRepositoryStub()
    service.cache_invalidator = CacheInvalidatorStub()
    service.read_model_builder = ReadModelBuilderStub()
    caplog.set_level(logging.INFO)

    service.run(sync_job_id=1, user_id=1)

    assert any("Refreshing expired Strava access token." in message for message in caplog.messages)
    assert any("Completed import service run." in message for message in caplog.messages)


def test_incremental_sync_uses_activity_checkpoint_for_after_filter() -> None:
    session = SessionStub()
    sync_job = SyncJobStub()
    sync_job.sync_type = "incremental_sync"
    oauth_token = OAuthTokenStub("enc:access-token", "enc:refresh-token", datetime.now(UTC) + timedelta(hours=1))
    strava_client = StravaClientStub()
    checkpoint_repo = CheckpointRepositoryStub()
    checkpoint_repo.value = {
        "user_id": 1,
        "sync_type": "activities",
        "checkpoint_value": "2026-03-01T06:00:00+00:00",
        "last_synced_at": datetime.now(UTC),
    }
    service = IncrementalSyncService(session, strava_client=strava_client, token_cipher=TokenCipherStub())
    service.sync_jobs = SyncJobRepositoryStub(sync_job)
    service.oauth_tokens = OAuthTokenRepositoryStub(oauth_token)
    service.activities = ActivityRepositoryStub()
    service.activity_streams = ActivityStreamRepositoryStub()
    service.checkpoints = checkpoint_repo
    service.cache_invalidator = CacheInvalidatorStub()
    service.read_model_builder = ReadModelBuilderStub()

    imported_count = service.run(sync_job_id=1, user_id=1)

    assert imported_count == 1
    assert strava_client.after == datetime.fromisoformat("2026-03-01T06:00:00+00:00")
    assert checkpoint_repo.value["sync_type"] == "activities"


def test_incremental_sync_continues_when_activity_stream_is_missing() -> None:
    session = SessionStub()
    sync_job = SyncJobStub()
    sync_job.sync_type = "incremental_sync"
    oauth_token = OAuthTokenStub("enc:access-token", "enc:refresh-token", datetime.now(UTC) + timedelta(hours=1))
    service = IncrementalSyncService(session, strava_client=MissingStreamStravaClientStub(), token_cipher=TokenCipherStub())
    service.sync_jobs = SyncJobRepositoryStub(sync_job)
    service.oauth_tokens = OAuthTokenRepositoryStub(oauth_token)
    service.activities = ActivityRepositoryStub()
    service.activity_streams = ActivityStreamRepositoryStub()
    service.checkpoints = CheckpointRepositoryStub()
    service.cache_invalidator = CacheInvalidatorStub()
    service.read_model_builder = ReadModelBuilderStub()

    imported_count = service.run(sync_job_id=1, user_id=1)

    assert imported_count == 1
    assert sync_job.status == "completed"
    assert 100 in service.activities.by_id
    assert service.activity_streams.by_activity_id == {}


def test_incremental_sync_uses_latest_local_activity_when_checkpoint_is_missing() -> None:
    session = SessionStub()
    sync_job = SyncJobStub()
    sync_job.sync_type = "incremental_sync"
    oauth_token = OAuthTokenStub("enc:access-token", "enc:refresh-token", datetime.now(UTC) + timedelta(hours=1))
    strava_client = StravaClientStub()
    service = IncrementalSyncService(session, strava_client=strava_client, token_cipher=TokenCipherStub())
    service.sync_jobs = SyncJobRepositoryStub(sync_job)
    service.oauth_tokens = OAuthTokenRepositoryStub(oauth_token)
    service.activities = ActivityRepositoryStub()
    service.activities.latest_start_date_utc = datetime.fromisoformat("2026-03-07T06:00:00+00:00")
    service.activity_streams = ActivityStreamRepositoryStub()
    service.checkpoints = CheckpointRepositoryStub()
    service.cache_invalidator = CacheInvalidatorStub()
    service.read_model_builder = ReadModelBuilderStub()

    imported_count = service.run(sync_job_id=1, user_id=1)

    assert imported_count == 1
    assert strava_client.after == datetime.fromisoformat("2026-03-07T06:00:00+00:00")


def test_incremental_sync_skips_already_imported_activities() -> None:
    session = SessionStub()
    sync_job = SyncJobStub()
    sync_job.sync_type = "incremental_sync"
    oauth_token = OAuthTokenStub("enc:access-token", "enc:refresh-token", datetime.now(UTC) + timedelta(hours=1))
    strava_client = StravaClientStub()
    service = IncrementalSyncService(session, strava_client=strava_client, token_cipher=TokenCipherStub())
    service.sync_jobs = SyncJobRepositoryStub(sync_job)
    service.oauth_tokens = OAuthTokenRepositoryStub(oauth_token)
    service.activities = ActivityRepositoryStub()
    service.activities.existing_strava_ids = {100}
    service.activity_streams = ActivityStreamRepositoryStub()
    service.checkpoints = CheckpointRepositoryStub()
    service.cache_invalidator = CacheInvalidatorStub()
    service.read_model_builder = ReadModelBuilderStub()

    imported_count = service.run(sync_job_id=1, user_id=1)

    assert imported_count == 0
    assert sync_job.status == "completed"
    assert sync_job.progress_total == 0
    assert strava_client.stream_calls == []
