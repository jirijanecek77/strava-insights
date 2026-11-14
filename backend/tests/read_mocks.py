"""Repository mocks shared by read-service and HTTP contract tests."""

from dataclasses import dataclass
from unittest.mock import Mock

from app.application.activities import rename
from app.application.read_models import activities, dashboard
from app.infrastructure.db.models.activity import Activity


@dataclass
class ActivityReadMocks:
    activities: Mock
    streams: Mock
    splits: Mock
    best_efforts: Mock
    user_profiles: Mock
    coaching: Mock


def mock_activity_repositories(monkeypatch, rows: list[Activity]) -> ActivityReadMocks:
    mocks = ActivityReadMocks(
        *[
            Mock(spec=cls)
            for cls in (
                activities.ActivityRepository,
                activities.ActivityStreamRepository,
                activities.ActivitySplitsRepository,
                activities.BestEffortRepository,
                activities.UserProfileRepository,
                activities.CoachingRepository,
            )
        ]
    )
    for name in (
            "activities",
            "streams",
            "splits",
            "best_efforts",
            "user_profiles",
            "coaching",
    ):
        repository = getattr(mocks, name)
        class_name = {
            "activities": "ActivityRepository",
            "streams": "ActivityStreamRepository",
            "splits": "ActivitySplitsRepository",
            "best_efforts": "BestEffortRepository",
            "user_profiles": "UserProfileRepository",
            "coaching": "CoachingRepository",
        }[name]
        monkeypatch.setattr(activities, class_name, Mock(return_value=repository))
    monkeypatch.setattr(
        rename, "ActivityRepository", Mock(return_value=mocks.activities)
    )
    monkeypatch.setattr(
        dashboard, "ActivityRepository", Mock(return_value=mocks.activities)
    )
    mocks.activities.get_by_id_for_user.side_effect = lambda activity_id, user_id: next(
        (row for row in rows if row.id == activity_id and row.user_id == user_id), None
    )
    mocks.activities.list_for_user.return_value = rows
    mocks.activities.list_with_hr_and_speed.return_value = rows
    mocks.activities.get_route_attempt_group.return_value = None
    mocks.streams.get_for_activity.return_value = None
    mocks.splits.get_for_activity.return_value = None
    mocks.best_efforts.list_for_user.return_value = []
    mocks.user_profiles.get_effective_for_user.return_value = None
    mocks.coaching.get_activity_note.return_value = None
    return mocks
