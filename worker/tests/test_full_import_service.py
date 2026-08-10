from datetime import UTC, datetime

from app.intervals_client import (
    IntervalsActivityStreamNotFoundError,
    IntervalsApiClient,
)
from app.services.sync_import import FullImportService, IncrementalSyncService


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


class IntervalsCredentialStub:
    def __init__(self, athlete_id: str, api_key_encrypted: str) -> None:
        self.athlete_id = athlete_id
        self.api_key_encrypted = api_key_encrypted


class ActivityStub:
    def __init__(self, activity_id: int | None = None) -> None:
        self.id = activity_id


class ActivityStreamStub:
    def __init__(self, activity_id: int) -> None:
        self.activity_id = activity_id


def test_intervals_api_client_formats_athlete_id_for_intervals_urls() -> None:
    assert IntervalsApiClient.format_athlete_id("632291") == "i632291"
    assert IntervalsApiClient.format_athlete_id("i632291") == "i632291"


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


class IntervalsCredentialRepositoryStub:
    def __init__(self, credential) -> None:
        self.credential = credential

    def get_for_user(self, _user_id: int):
        return self.credential


class ActivityRepositoryStub:
    def __init__(self) -> None:
        self.by_id = {}
        self.counter = 1
        self.latest_start_date_utc = None
        self.existing_source_activity_ids = set()

    def get_by_source_activity_id(self, _user_id: int, source_activity_id: int):
        return self.by_id.get(source_activity_id)

    def list_existing_source_activity_ids_for_user(
        self, _user_id: int, source_activity_ids: list[int]
    ):
        return {
            source_activity_id
            for source_activity_id in source_activity_ids
            if source_activity_id in self.existing_source_activity_ids
        }

    def save(self, activity):
        if getattr(activity, "id", None) is None:
            activity.id = self.counter
            self.counter += 1
        self.by_id[activity.strava_activity_id] = activity
        return activity

    def get_latest_start_date_utc_for_user(self, _user_id: int):
        return self.latest_start_date_utc

    def update_routes_for_user(self, _user_id: int, assignments):
        changed = 0
        for source_activity_id, (route_id, route_name) in assignments.items():
            activity = self.by_id.get(source_activity_id)
            if activity is None:
                continue
            activity.intervals_route_id = route_id
            activity.intervals_route_name = route_name
            changed += 1
        return changed


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
        self.values = {}

    def get_for_user(self, _user_id: int, sync_type: str):
        value = self.values.get(sync_type)
        if value is None:
            return None
        return type("CheckpointStub", (), value)()

    def upsert(self, **kwargs):
        self.values[kwargs["sync_type"]] = kwargs


class CacheInvalidatorStub:
    def __init__(self) -> None:
        self.user_ids: list[int] = []

    def invalidate_user(self, user_id: int) -> int:
        self.user_ids.append(user_id)
        return 1


class ReadModelBuilderStub:
    def __init__(self) -> None:
        self.user_ids: list[int] = []
        self.source_run_efforts = None

    def rebuild_for_user(self, user_id: int, *, source_run_efforts=None) -> None:
        self.user_ids.append(user_id)
        self.source_run_efforts = source_run_efforts


class TokenCipherStub:
    def encrypt(self, value: str) -> str:
        return f"enc:{value}"

    def decrypt(self, value: str) -> str:
        return value.replace("enc:", "", 1)


class IntervalsClientStub:
    def __init__(self) -> None:
        self.after = None
        self.stream_calls: list[int] = []

    @staticmethod
    def parse_activity_id(value) -> int:
        text = str(value)
        return int(text[1:] if text.startswith("i") else text)

    def get_activities(self, athlete_id: str, api_key: str, *, after=None):
        assert athlete_id == "12345"
        assert api_key == "access-token"
        self.after = after
        return [
            {
                "id": "i100",
                "name": "Morning Run",
                "type": "Run",
                "start_date": "2026-03-09T06:00:00Z",
                "start_date_local": "2026-03-09T07:00:00+01:00",
                "distance": 10000.0,
                "moving_time": 2700,
                "elapsed_time": 2800,
                "total_elevation_gain": 100.0,
                "average_speed": 3.7,
                "max_speed": 4.5,
                "average_heartrate": 150.0,
                "average_cadence": 84.0,
                "route_id": 42,
            }
        ]

    def get_activity_stream(self, api_key: str, activity_id: int):
        assert api_key == "access-token"
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

    def get_activity_route_assignments(self, athlete_id: str, api_key: str):
        assert athlete_id == "12345"
        assert api_key == "access-token"
        return [{"id": "i100", "route_id": 42}]

    def get_routes(self, athlete_id: str, api_key: str):
        assert athlete_id == "12345"
        assert api_key == "access-token"
        return [{"id": 42, "name": "River Loop"}]

    def get_run_pace_curves(self, athlete_id: str, api_key: str, *, distances_meters):
        assert distances_meters == [1000.0, 5000.0, 10000.0, 21097.5]
        return {
            "distances": distances_meters,
            "curves": [{"id": "i100", "secs": [240, 1400, 3000]}],
        }


class MissingStreamIntervalsClientStub(IntervalsClientStub):
    def get_activity_stream(self, api_key: str, activity_id: int):
        raise IntervalsActivityStreamNotFoundError(activity_id)


def test_full_import_service_imports_activities_updates_progress_and_checkpoint() -> (
    None
):
    session = SessionStub()
    sync_job = SyncJobStub()
    service = FullImportService(
        session, intervals_client=IntervalsClientStub(), token_cipher=TokenCipherStub()
    )
    service.sync_jobs = SyncJobRepositoryStub(sync_job)
    service.intervals_credentials = IntervalsCredentialRepositoryStub(
        IntervalsCredentialStub("12345", "enc:access-token")
    )
    service.activities = ActivityRepositoryStub()
    service.activity_streams = ActivityStreamRepositoryStub()
    service.checkpoints = CheckpointRepositoryStub()
    service.cache_invalidator = CacheInvalidatorStub()
    service.read_model_builder = ReadModelBuilderStub()

    imported_count = service.run(sync_job_id=1, user_id=1)

    assert imported_count == 1
    assert sync_job.status == "completed"
    assert sync_job.progress_completed == 1
    assert (
        service.checkpoints.values["activities"]["checkpoint_value"]
        == "2026-03-09T06:00:00+00:00"
    )
    assert service.checkpoints.values["analytics_model"]["checkpoint_value"] == "2"
    assert 100 in service.activities.by_id
    assert service.activities.by_id[100].distance_km == 10
    assert service.activities.by_id[100].moving_time_display == "45:00"
    assert service.activities.by_id[100].average_pace_display == "4:30"
    assert service.activities.by_id[100].summary_metric_display == "4:30 /km"
    assert service.activity_streams.by_activity_id[1].heartrate_stream == {
        "data": [145, 146, 150, 152]
    }
    assert service.activities.by_id[100].intervals_route_name == "River Loop"
    assert service.read_model_builder.user_ids == [1]
    assert service.cache_invalidator.user_ids == [1]


def test_incremental_sync_uses_activity_checkpoint_for_after_filter() -> None:
    session = SessionStub()
    sync_job = SyncJobStub()
    sync_job.sync_type = "incremental_sync"
    intervals_client = IntervalsClientStub()
    checkpoint_repo = CheckpointRepositoryStub()
    checkpoint_repo.values["activities"] = {
        "user_id": 1,
        "sync_type": "activities",
        "checkpoint_value": "2026-03-01T06:00:00+00:00",
        "last_synced_at": datetime.now(UTC),
    }
    service = IncrementalSyncService(
        session, intervals_client=intervals_client, token_cipher=TokenCipherStub()
    )
    service.sync_jobs = SyncJobRepositoryStub(sync_job)
    service.intervals_credentials = IntervalsCredentialRepositoryStub(
        IntervalsCredentialStub("12345", "enc:access-token")
    )
    service.activities = ActivityRepositoryStub()
    service.activity_streams = ActivityStreamRepositoryStub()
    service.checkpoints = checkpoint_repo
    service.cache_invalidator = CacheInvalidatorStub()
    service.read_model_builder = ReadModelBuilderStub()

    imported_count = service.run(sync_job_id=1, user_id=1)

    assert imported_count == 1
    assert intervals_client.after == datetime.fromisoformat("2026-03-01T06:00:00+00:00")
    assert checkpoint_repo.values["activities"]["sync_type"] == "activities"


def test_incremental_sync_continues_when_activity_stream_is_missing() -> None:
    session = SessionStub()
    sync_job = SyncJobStub()
    sync_job.sync_type = "incremental_sync"
    service = IncrementalSyncService(
        session,
        intervals_client=MissingStreamIntervalsClientStub(),
        token_cipher=TokenCipherStub(),
    )
    service.sync_jobs = SyncJobRepositoryStub(sync_job)
    service.intervals_credentials = IntervalsCredentialRepositoryStub(
        IntervalsCredentialStub("12345", "enc:access-token")
    )
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


def test_incremental_sync_uses_latest_local_activity_when_checkpoint_is_missing() -> (
    None
):
    session = SessionStub()
    sync_job = SyncJobStub()
    sync_job.sync_type = "incremental_sync"
    intervals_client = IntervalsClientStub()
    service = IncrementalSyncService(
        session, intervals_client=intervals_client, token_cipher=TokenCipherStub()
    )
    service.sync_jobs = SyncJobRepositoryStub(sync_job)
    service.intervals_credentials = IntervalsCredentialRepositoryStub(
        IntervalsCredentialStub("12345", "enc:access-token")
    )
    service.activities = ActivityRepositoryStub()
    service.activities.latest_start_date_utc = datetime.fromisoformat(
        "2026-03-07T06:00:00+00:00"
    )
    service.activity_streams = ActivityStreamRepositoryStub()
    service.checkpoints = CheckpointRepositoryStub()
    service.cache_invalidator = CacheInvalidatorStub()
    service.read_model_builder = ReadModelBuilderStub()

    imported_count = service.run(sync_job_id=1, user_id=1)

    assert imported_count == 1
    assert intervals_client.after == datetime.fromisoformat("2026-03-07T06:00:00+00:00")


def test_incremental_sync_skips_already_imported_activities() -> None:
    session = SessionStub()
    sync_job = SyncJobStub()
    sync_job.sync_type = "incremental_sync"
    intervals_client = IntervalsClientStub()
    service = IncrementalSyncService(
        session, intervals_client=intervals_client, token_cipher=TokenCipherStub()
    )
    service.sync_jobs = SyncJobRepositoryStub(sync_job)
    service.intervals_credentials = IntervalsCredentialRepositoryStub(
        IntervalsCredentialStub("12345", "enc:access-token")
    )
    service.activities = ActivityRepositoryStub()
    service.activities.existing_source_activity_ids = {100}
    service.activity_streams = ActivityStreamRepositoryStub()
    service.checkpoints = CheckpointRepositoryStub()
    service.checkpoints.values["analytics_model"] = {
        "user_id": 1,
        "sync_type": "analytics_model",
        "checkpoint_value": "2",
        "last_synced_at": datetime.now(UTC),
    }
    service.cache_invalidator = CacheInvalidatorStub()
    service.read_model_builder = ReadModelBuilderStub()

    imported_count = service.run(sync_job_id=1, user_id=1)

    assert imported_count == 0
    assert sync_job.status == "completed"
    assert sync_job.progress_total == 0
    assert intervals_client.stream_calls == []
    assert service.read_model_builder.user_ids == []
