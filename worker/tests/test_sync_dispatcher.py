from app.services.sync_dispatcher import SyncDispatchDispatcher
from dataclasses import dataclass


@dataclass
class PendingDispatch:
    id: int
    sync_job_id: int
    user_id: int
    sync_type: str
    payload_json: dict[str, int]
    status: str = "pending"
    attempt_count: int = 0
    last_error: str | None = None


class DispatchRepositoryStub:
    def __init__(self, dispatch: PendingDispatch) -> None:
        self.dispatch = dispatch

    def claim_pending(self, *, limit: int) -> list[PendingDispatch]:
        if self.dispatch.status != "pending" or limit < 1:
            return []
        self.dispatch.status = "dispatching"
        self.dispatch.attempt_count += 1
        return [self.dispatch]

    def mark_dispatched(self, dispatch: PendingDispatch) -> None:
        dispatch.status = "dispatched"

    def reschedule_after_publish_failure(
            self, dispatch: PendingDispatch, *, error_message: str
    ) -> None:
        dispatch.status = "pending"
        dispatch.last_error = error_message


class FlakyQueueClient:
    def __init__(self) -> None:
        self.publish_attempts = 0
        self.published: list[tuple[str, dict[str, int]]] = []

    def send_task(self, task_name: str, *, kwargs: dict[str, int]) -> None:
        self.publish_attempts += 1
        if self.publish_attempts == 1:
            raise ConnectionError("Redis is unavailable")
        self.published.append((task_name, kwargs))


def test_dispatcher_retries_a_durable_command_after_broker_recovers() -> None:
    dispatch = PendingDispatch(
        id=5,
        sync_job_id=42,
        user_id=7,
        sync_type="full_import",
        payload_json={"sync_job_id": 42, "user_id": 7},
    )
    repository = DispatchRepositoryStub(dispatch)
    queue = FlakyQueueClient()
    dispatcher = SyncDispatchDispatcher(repository=repository, queue_client=queue)

    assert dispatcher.dispatch_pending() == 0
    assert dispatch.status == "pending"
    assert dispatch.attempt_count == 1
    assert dispatch.last_error == "Redis is unavailable"

    assert dispatcher.dispatch_pending() == 1
    assert dispatch.status == "dispatched"
    assert dispatch.attempt_count == 2
    assert queue.published == [
        ("app.tasks.sync.run_full_import", {"sync_job_id": 42, "user_id": 7})
    ]
