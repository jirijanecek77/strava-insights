from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from app.models import Activity, ActivityStream
from app.services.activity_import_writer import ActivityImportWriter
from app.services.fit_import import (
    FitImportError,
    FitImportService,
    ParsedFitActivity,
)
from app.services.route_index_builder import RouteIndexStats


class SessionStub:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def flush(self) -> None:
        pass

    def begin_nested(self):
        return nullcontext()


class UserStub:
    def __init__(self, user_id: int = 1) -> None:
        self.id = user_id
        self.display_name = "Only User"


class UserRepositoryStub:
    def __init__(self, users: list[UserStub]) -> None:
        self.users = users

    def list_all(self) -> list[UserStub]:
        return self.users


class ActivityRepositoryStub:
    def __init__(self, existing: list[Activity] | None = None) -> None:
        self.activities = existing or []
        self.counter = 100

    def get_by_source_activity_id(self, user_id: int, source_activity_id: int):
        for activity in self.activities:
            if (
                activity.user_id == user_id
                and activity.strava_activity_id == source_activity_id
            ):
                return activity
        return None

    def save(self, activity):
        if getattr(activity, "id", None) is None:
            activity.id = self.counter
            self.counter += 1
            self.activities.append(activity)
        return activity

    def list_for_user(self, user_id: int, sport_type: str | None = None):
        activities = [
            activity for activity in self.activities if activity.user_id == user_id
        ]
        if sport_type is not None:
            activities = [
                activity for activity in activities if activity.sport_type == sport_type
            ]
        return activities


class ActivityStreamRepositoryStub:
    def __init__(self) -> None:
        self.streams: dict[int, ActivityStream] = {}

    def get_by_activity_id(self, activity_id: int):
        return self.streams.get(activity_id)

    def save(self, activity_stream):
        self.streams[activity_stream.activity_id] = activity_stream
        return activity_stream


class CheckpointRepositoryStub:
    def __init__(self) -> None:
        self.values: dict[tuple[int, str], dict[str, Any]] = {}

    def get_for_user(self, user_id: int, sync_type: str):
        return self.values.get((user_id, sync_type))

    def upsert(self, **kwargs) -> None:
        self.values[(kwargs["user_id"], kwargs["sync_type"])] = kwargs


class CacheInvalidatorStub:
    def __init__(self) -> None:
        self.user_ids: list[int] = []

    def invalidate_user(self, user_id: int) -> int:
        self.user_ids.append(user_id)
        return 1


class ReadModelBuilderStub:
    def __init__(self) -> None:
        self.calls: list[tuple[int, dict]] = []

    def rebuild_for_user(self, user_id: int, *, source_run_efforts=None) -> None:
        self.calls.append((user_id, source_run_efforts))


class RouteIndexBuilderStub:
    def __init__(self) -> None:
        self.user_ids: list[int] = []

    def rebuild_for_user(self, user_id: int) -> RouteIndexStats:
        self.user_ids.append(user_id)
        return RouteIndexStats(
            eligible_activity_count=1,
            excluded_activity_count=0,
            route_group_count=0,
            matched_activity_count=0,
            compared_pair_count=0,
            matched_pair_count=0,
        )


class ParserStub:
    def __init__(
        self, parsed_by_name: dict[str, ParsedFitActivity | Exception]
    ) -> None:
        self.parsed_by_name = parsed_by_name

    def parse(self, path: Path) -> ParsedFitActivity:
        result = self.parsed_by_name[path.name]
        if isinstance(result, Exception):
            raise result
        return result


def _parsed_activity(
    *,
    source_id: int,
    start_date_local: str,
    distance: float,
    sport_type: str = "Run",
) -> ParsedFitActivity:
    return ParsedFitActivity(
        source_activity_id=source_id,
        payload={
            "id": source_id,
            "name": "Imported FIT",
            "type": sport_type,
            "start_date": start_date_local,
            "start_date_local": start_date_local,
            "distance": distance,
            "moving_time": 1800,
            "elapsed_time": 1810,
            "average_speed": distance / 1800,
        },
        stream_payload={
            "time": {"data": [0, 900, 1800]},
            "distance": {"data": [0, distance / 2, distance]},
            "latlng": {"data": [[50.0, 14.0], [50.01, 14.01], [50.02, 14.02]]},
            "altitude": {"data": [300, 305, 310]},
            "velocity_smooth": {"data": [2.5, 2.7, 2.8]},
            "heartrate": {"data": [140, 145, 150]},
        },
    )


def _existing_activity(*, activity_id: int, distance: float) -> Activity:
    return Activity(
        id=activity_id,
        user_id=1,
        strava_activity_id=12345,
        name="Existing run",
        sport_type="Run",
        start_date_utc=datetime(2026, 3, 9, 6, 0, tzinfo=UTC),
        start_date_local=datetime(2026, 3, 9, 7, 0, tzinfo=UTC),
        distance_meters=distance,
        moving_time_seconds=1800,
    )


def _service(
    *,
    parser: ParserStub,
    activities: ActivityRepositoryStub,
    users: list[UserStub] | None = None,
):
    session = SessionStub()
    service = FitImportService(
        cast(Any, session),
        parser=cast(Any, parser),
        cache_invalidator=cast(Any, CacheInvalidatorStub()),
        read_model_builder=cast(Any, ReadModelBuilderStub()),
        route_index_builder=cast(Any, RouteIndexBuilderStub()),
    )
    service_as_any = cast(Any, service)
    service_as_any.users = UserRepositoryStub(users or [UserStub()])
    service_as_any.activities = activities
    service_as_any.activity_streams = ActivityStreamRepositoryStub()
    service_as_any.checkpoints = CheckpointRepositoryStub()
    service.writer = ActivityImportWriter(
        activities=cast(Any, service.activities),
        activity_streams=cast(Any, service.activity_streams),
    )
    return service, session


def test_fit_import_imports_new_files_skips_duplicates_and_continues_after_failure(
    tmp_path: Path,
) -> None:
    duplicate_file = tmp_path / "duplicate.fit"
    new_file = tmp_path / "new.fit"
    broken_file = tmp_path / "broken.fit"
    for file in (duplicate_file, new_file, broken_file):
        file.write_bytes(b"fit")
    parser = ParserStub(
        {
            "broken.fit": FitImportError("bad fit file"),
            "duplicate.fit": _parsed_activity(
                source_id=-1,
                start_date_local="2026-03-09T07:30:00+01:00",
                distance=10490,
            ),
            "new.fit": _parsed_activity(
                source_id=-2,
                start_date_local="2026-03-10T07:30:00+01:00",
                distance=12000,
            ),
        }
    )
    service, session = _service(
        parser=parser,
        activities=ActivityRepositoryStub(
            existing=[_existing_activity(activity_id=10, distance=10000)]
        ),
    )

    summary = service.run(import_path=tmp_path)

    assert summary.scanned_files == 3
    assert summary.imported_count == 1
    assert summary.skipped_duplicate_count == 1
    assert summary.failed_count == 1
    assert len(service.activities.activities) == 2
    imported = service.activities.get_by_source_activity_id(1, -2)
    assert imported is not None
    assert imported.distance_km == 12
    assert imported.moving_time_display == "30:00"
    assert service.activity_streams.streams[imported.id].heartrate_stream == {
        "data": [140, 145, 150]
    }
    assert service.read_model_builder.calls == [(1, {})]
    assert service.route_index_builder.user_ids == [1]
    assert service.cache_invalidator.user_ids == [1]
    assert session.rollbacks == 1


def test_fit_import_imports_same_date_activity_outside_distance_tolerance(
    tmp_path: Path,
) -> None:
    fit_file = tmp_path / "outside-tolerance.fit"
    fit_file.write_bytes(b"fit")
    service, _session = _service(
        parser=ParserStub(
            {
                "outside-tolerance.fit": _parsed_activity(
                    source_id=-3,
                    start_date_local="2026-03-09T08:00:00+01:00",
                    distance=10600,
                )
            }
        ),
        activities=ActivityRepositoryStub(
            existing=[_existing_activity(activity_id=10, distance=10000)]
        ),
    )

    summary = service.run(import_path=tmp_path)

    assert summary.imported_count == 1
    assert summary.skipped_duplicate_count == 0
    assert service.activities.get_by_source_activity_id(1, -3) is not None


def test_fit_import_requires_exactly_one_user(tmp_path: Path) -> None:
    fit_file = tmp_path / "new.fit"
    fit_file.write_bytes(b"fit")
    service, _session = _service(
        parser=ParserStub(
            {
                "new.fit": _parsed_activity(
                    source_id=-4,
                    start_date_local="2026-03-10T07:30:00+01:00",
                    distance=12000,
                )
            }
        ),
        activities=ActivityRepositoryStub(),
        users=[UserStub(1), UserStub(2)],
    )

    try:
        service.run(import_path=tmp_path)
    except FitImportError as exc:
        assert "Expected exactly one user" in str(exc)
    else:
        raise AssertionError("FitImportError was not raised.")
