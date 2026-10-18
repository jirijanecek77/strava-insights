from contextlib import nullcontext
from types import SimpleNamespace

from app.services.local_route_matcher import ROUTE_MODEL_VERSION
from app.services.sync_import import (
    ANALYTICS_CHECKPOINT_TYPE,
    ANALYTICS_MODEL_VERSION,
    DERIVED_ACTIVITIES_CHECKPOINT_TYPE,
    ROUTE_CHECKPOINT_TYPE,
    BaseImportService,
)


class CheckpointRepositoryStub:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = dict(values)

    def get_for_user(self, _user_id: int, sync_type: str):
        value = self.values.get(sync_type)
        return None if value is None else SimpleNamespace(checkpoint_value=value)

    def upsert(self, *, user_id: int, sync_type: str, checkpoint_value, last_synced_at) -> None:
        self.values[sync_type] = checkpoint_value


class ActivityRepositoryStub:
    def __init__(self, activities: list) -> None:
        self.activities = activities
        self.requested: tuple[list[int], int] | None = None

    def list_by_ids_or_after_id(self, _user_id: int, *, activity_ids: list[int], after_id: int):
        self.requested = (activity_ids, after_id)
        return [
            activity
            for activity in self.activities
            if activity.id > after_id or activity.id in activity_ids
        ]

    def get_max_id_for_user(self, _user_id: int) -> int | None:
        return max((activity.id for activity in self.activities), default=None)


class ReadModelBuilderStub:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[int]]] = []

    def rebuild_for_user(self, _user_id: int, *, source_run_efforts) -> None:
        self.calls.append(("rebuild", []))

    def update_for_activities(self, _user_id: int, activities: list, *, source_run_efforts) -> None:
        self.calls.append(("update", [activity.id for activity in activities]))


class RouteIndexBuilderStub:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[str, list[int]]] = []

    def rebuild_for_user(self, _user_id: int) -> None:
        self.calls.append(("rebuild", []))

    def update_for_activities(self, _user_id: int, activities: list) -> None:
        if self.fail:
            raise RuntimeError("route update failed")
        self.calls.append(("update", [activity.id for activity in activities]))


CURRENT_CHECKPOINTS = {
    ANALYTICS_CHECKPOINT_TYPE: ANALYTICS_MODEL_VERSION,
    ROUTE_CHECKPOINT_TYPE: ROUTE_MODEL_VERSION,
    DERIVED_ACTIVITIES_CHECKPOINT_TYPE: "2",
}


def _service(*, checkpoints: dict[str, str], route_fail: bool = False) -> BaseImportService:
    service = BaseImportService.__new__(BaseImportService)
    service.session = SimpleNamespace(begin_nested=nullcontext)
    service.checkpoints = CheckpointRepositoryStub(checkpoints)
    service.activities = ActivityRepositoryStub(
        [SimpleNamespace(id=activity_id) for activity_id in (1, 2, 3, 4)]
    )
    service.read_model_builder = ReadModelBuilderStub()
    service.route_index_builder = RouteIndexBuilderStub(fail=route_fail)
    return service


def _sync_job(*, sync_type: str = "incremental_sync", source: str = "daily_schedule"):
    return SimpleNamespace(id=5, sync_type=sync_type, metadata_json={"source": source})


def test_incremental_sync_processes_only_activities_after_the_watermark() -> None:
    service = _service(checkpoints=CURRENT_CHECKPOINTS)

    changed, routes_updated = service._update_derived_data(
        sync_job=_sync_job(), user_id=1, backfilled_activity_ids=[1]
    )

    assert (changed, routes_updated) == (True, True)
    assert service.activities.requested == ([1], 2)
    assert service.read_model_builder.calls == [("update", [1, 3, 4])]
    assert service.route_index_builder.calls == [("update", [1, 3, 4])]
    assert service.checkpoints.values[DERIVED_ACTIVITIES_CHECKPOINT_TYPE] == "4"


def test_incremental_sync_without_new_activities_skips_derived_data() -> None:
    service = _service(
        checkpoints={**CURRENT_CHECKPOINTS, DERIVED_ACTIVITIES_CHECKPOINT_TYPE: "4"}
    )

    changed, routes_updated = service._update_derived_data(
        sync_job=_sync_job(source="manual_refresh"), user_id=1, backfilled_activity_ids=[]
    )

    assert (changed, routes_updated) == (False, True)
    assert service.read_model_builder.calls == []
    assert service.route_index_builder.calls == []


def test_recalculate_all_rebuilds_every_derived_model() -> None:
    service = _service(checkpoints=CURRENT_CHECKPOINTS)

    service._update_derived_data(
        sync_job=_sync_job(source="full_recompute"), user_id=1, backfilled_activity_ids=[]
    )

    assert service.activities.requested is None
    assert service.read_model_builder.calls == [("rebuild", [])]
    assert service.route_index_builder.calls == [("rebuild", [])]
    assert service.checkpoints.values[DERIVED_ACTIVITIES_CHECKPOINT_TYPE] == "4"


def test_missing_watermark_triggers_full_recomputation() -> None:
    checkpoints = dict(CURRENT_CHECKPOINTS)
    del checkpoints[DERIVED_ACTIVITIES_CHECKPOINT_TYPE]
    service = _service(checkpoints=checkpoints)

    service._update_derived_data(sync_job=_sync_job(), user_id=1, backfilled_activity_ids=[])

    assert service.read_model_builder.calls == [("rebuild", [])]
    assert service.route_index_builder.calls == [("rebuild", [])]


def test_stale_route_model_rebuilds_routes_and_updates_analytics_incrementally() -> None:
    service = _service(checkpoints={**CURRENT_CHECKPOINTS, ROUTE_CHECKPOINT_TYPE: "0"})

    service._update_derived_data(sync_job=_sync_job(), user_id=1, backfilled_activity_ids=[])

    assert service.read_model_builder.calls == [("update", [3, 4])]
    assert service.route_index_builder.calls == [("rebuild", [])]


def test_failed_route_update_keeps_the_watermark_for_a_retry() -> None:
    service = _service(checkpoints=CURRENT_CHECKPOINTS, route_fail=True)

    changed, routes_updated = service._update_derived_data(
        sync_job=_sync_job(), user_id=1, backfilled_activity_ids=[]
    )

    assert (changed, routes_updated) == (True, False)
    assert service.checkpoints.values[DERIVED_ACTIVITIES_CHECKPOINT_TYPE] == "2"
