from datetime import UTC, datetime
from decimal import Decimal

from app.services.read_model_builder import ReadModelBuilder


class ActivityStub:
    def __init__(
        self,
        *,
        activity_id: int,
        sport_type: str,
        start_date_utc: datetime,
        start_date_local: datetime,
        distance_meters: str,
        moving_time_seconds: int,
        total_elevation_gain_meters: str | None,
        difficulty_score: str | None,
    ) -> None:
        self.id = activity_id
        self.sport_type = sport_type
        self.start_date_utc = start_date_utc
        self.start_date_local = start_date_local
        self.distance_meters = Decimal(distance_meters)
        self.moving_time_seconds = moving_time_seconds
        self.total_elevation_gain_meters = None if total_elevation_gain_meters is None else Decimal(total_elevation_gain_meters)
        self.difficulty_score = None if difficulty_score is None else Decimal(difficulty_score)


class ActivityStreamStub:
    def __init__(self, activity_id: int, distance_data: list[float], time_data: list[int]) -> None:
        self.activity_id = activity_id
        self.distance_stream = {"data": distance_data}
        self.time_stream = {"data": time_data}


class ActivityRepositoryStub:
    def __init__(self, activities) -> None:
        self.activities = activities

    def list_for_user(self, _user_id: int):
        return self.activities


class ActivityStreamRepositoryStub:
    def __init__(self, streams) -> None:
        self.streams = streams

    def get_by_activity_ids(self, _activity_ids):
        return self.streams


class PeriodSummaryRepositoryStub:
    def __init__(self) -> None:
        self.summaries = None

    def replace_for_user(self, *, user_id: int, summaries):
        self.user_id = user_id
        self.summaries = summaries


class BestEffortRepositoryStub:
    def __init__(self) -> None:
        self.efforts = None

    def replace_for_user(self, *, user_id: int, efforts):
        self.user_id = user_id
        self.efforts = efforts


class ActivityBestEffortRepositoryStub:
    def __init__(self) -> None:
        self.efforts = None
        self.activity_ids = None

    def replace_for_activities(self, *, activity_ids, efforts):
        self.activity_ids = activity_ids
        self.efforts = efforts


def test_read_model_builder_rebuilds_period_summaries_and_best_efforts() -> None:
    builder = ReadModelBuilder(session=None)
    builder.activities = ActivityRepositoryStub(
        [
            ActivityStub(
                activity_id=1,
                sport_type="Run",
                start_date_utc=datetime(2026, 3, 9, tzinfo=UTC),
                start_date_local=datetime(2026, 3, 9, 7, 0, tzinfo=UTC),
                distance_meters="10000",
                moving_time_seconds=2700,
                total_elevation_gain_meters="100",
                difficulty_score="1.25",
            ),
            ActivityStub(
                activity_id=2,
                sport_type="Ride",
                start_date_utc=datetime(2026, 3, 8, tzinfo=UTC),
                start_date_local=datetime(2026, 3, 8, 8, 0, tzinfo=UTC),
                distance_meters="30000",
                moving_time_seconds=3600,
                total_elevation_gain_meters="250",
                difficulty_score="0.50",
            ),
        ]
    )
    builder.activity_streams = ActivityStreamRepositoryStub(
        [
            ActivityStreamStub(
                activity_id=1,
                distance_data=[0, 1000, 5000, 10000, 21097.5],
                time_data=[0, 240, 1400, 3000, 7000],
            )
        ]
    )
    builder.period_summaries = PeriodSummaryRepositoryStub()
    builder.best_efforts = BestEffortRepositoryStub()
    builder.activity_best_efforts = ActivityBestEffortRepositoryStub()

    builder.rebuild_for_user(7)

    assert builder.period_summaries.user_id == 7
    assert len(builder.period_summaries.summaries) == 6
    assert builder.best_efforts.user_id == 7
    assert {effort.effort_code for effort in builder.best_efforts.efforts} == {"1km", "5km", "10km", "Half-Marathon"}
    assert builder.activity_best_efforts.activity_ids == [1, 2]
