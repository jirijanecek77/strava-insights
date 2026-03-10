from datetime import date, timedelta

from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.application.analytics.aggregations import ActivityAggregateInput, compare_periods, summarize_window
from app.domain.schemas.dashboard import DashboardResponse, PeriodComparisonSchema, PeriodSummarySchema, TrendsResponse
from app.infrastructure.repositories.activity_repository import ActivityRepository
from app.infrastructure.repositories.period_summary_repository import PeriodSummaryRepository


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _previous_month(value: date) -> date:
    if value.month == 1:
        return value.replace(year=value.year - 1, month=12, day=1)
    return value.replace(month=value.month - 1, day=1)


def _year_start(value: date) -> date:
    return value.replace(month=1, day=1)


def _week_start(value: date) -> date:
    return value - timedelta(days=value.weekday())


class DashboardReadService:
    def __init__(self, db_session: Session = Depends(get_db_session)) -> None:
        self.period_summaries = PeriodSummaryRepository(db_session)
        self.activities = ActivityRepository(db_session)

    def get_dashboard(self, user_id: int, *, today: date, sport_type: str | None = None) -> DashboardResponse:
        current_month = _month_start(today)
        previous_month = _previous_month(current_month)
        current_year = _year_start(today)
        previous_year = current_year.replace(year=current_year.year - 1)
        return DashboardResponse(
            month=self._compare_period(user_id, "month", current_month, previous_month, sport_type=sport_type),
            year=self._compare_period(user_id, "year", current_year, previous_year, sport_type=sport_type),
        )

    def get_trends(self, user_id: int, *, period_type: str, sport_type: str | None = None) -> TrendsResponse:
        items = self.period_summaries.list_for_user(user_id, period_type=period_type, sport_type=sport_type)
        return TrendsResponse(
            period_type=period_type,
            items=[PeriodSummarySchema.model_validate(item, from_attributes=True) for item in items],
        )

    def get_comparisons(
        self,
        user_id: int,
        *,
        period_type: str,
        today: date,
        sport_type: str | None = None,
    ) -> list[PeriodComparisonSchema]:
        if period_type == "rolling_30d":
            return self._compare_rolling_30d(user_id, today=today, sport_type=sport_type)
        if period_type == "week":
            current = _week_start(today)
            previous = current - timedelta(days=7)
        elif period_type == "month":
            current = _month_start(today)
            previous = _previous_month(current)
        elif period_type == "year":
            current = _year_start(today)
            previous = _year_start(today).replace(year=today.year - 1)
        else:
            raise ValueError("Unsupported period_type.")
        return self._compare_period(user_id, period_type, current, previous, sport_type=sport_type)

    def _compare_rolling_30d(
        self,
        user_id: int,
        *,
        today: date,
        sport_type: str | None,
    ) -> list[PeriodComparisonSchema]:
        current_start = today - timedelta(days=29)
        previous_start = today - timedelta(days=59)
        previous_end = current_start - timedelta(days=1)
        current_activities = self.activities.list_for_user(user_id, sport_type=sport_type, date_from=current_start, date_to=today + timedelta(days=1))
        previous_activities = self.activities.list_for_user(user_id, sport_type=sport_type, date_from=previous_start, date_to=previous_end + timedelta(days=1))
        current_inputs = [self._to_aggregate_input(activity) for activity in current_activities]
        previous_inputs = [self._to_aggregate_input(activity) for activity in previous_activities]
        sports = sorted({item.sport_type for item in current_inputs + previous_inputs})
        comparisons: list[PeriodComparisonSchema] = []
        for sport in sports:
            comparison = compare_periods(
                current=summarize_window(current_inputs, sport_type=sport, window_type="rolling_30d", window_start=current_start),
                previous=summarize_window(previous_inputs, sport_type=sport, window_type="rolling_30d", window_start=previous_start),
            )
            comparisons.append(
                PeriodComparisonSchema(
                    current=None
                    if comparison["current"] is None
                    else PeriodSummarySchema.model_validate(comparison["current"], from_attributes=True),
                    previous=None
                    if comparison["previous"] is None
                    else PeriodSummarySchema.model_validate(comparison["previous"], from_attributes=True),
                    delta_distance_meters=comparison["delta_distance_meters"],
                    delta_moving_time_seconds=comparison["delta_moving_time_seconds"],
                    delta_activity_count=comparison["delta_activity_count"],
                    delta_average_speed_mps=comparison["delta_average_speed_mps"],
                    delta_average_pace_seconds_per_km=comparison["delta_average_pace_seconds_per_km"],
                )
            )
        return comparisons

    def _compare_period(
        self,
        user_id: int,
        period_type: str,
        current_start: date,
        previous_start: date,
        *,
        sport_type: str | None,
    ) -> list[PeriodComparisonSchema]:
        current_items = self.period_summaries.get_for_period(
            user_id,
            period_type=period_type,
            period_start=current_start,
            sport_type=sport_type,
        )
        previous_items = self.period_summaries.get_for_period(
            user_id,
            period_type=period_type,
            period_start=previous_start,
            sport_type=sport_type,
        )
        current_by_sport = {item.sport_type: item for item in current_items}
        previous_by_sport = {item.sport_type: item for item in previous_items}
        sports = sorted(set(current_by_sport) | set(previous_by_sport))
        comparisons: list[PeriodComparisonSchema] = []
        for sport in sports:
            comparison = compare_periods(current=current_by_sport.get(sport), previous=previous_by_sport.get(sport))
            comparisons.append(
                PeriodComparisonSchema(
                    current=None
                    if comparison["current"] is None
                    else PeriodSummarySchema.model_validate(comparison["current"], from_attributes=True),
                    previous=None
                    if comparison["previous"] is None
                    else PeriodSummarySchema.model_validate(comparison["previous"], from_attributes=True),
                    delta_distance_meters=comparison["delta_distance_meters"],
                    delta_moving_time_seconds=comparison["delta_moving_time_seconds"],
                    delta_activity_count=comparison["delta_activity_count"],
                    delta_average_speed_mps=comparison["delta_average_speed_mps"],
                    delta_average_pace_seconds_per_km=comparison["delta_average_pace_seconds_per_km"],
                )
            )
        return comparisons

    @staticmethod
    def _to_aggregate_input(activity) -> ActivityAggregateInput:
        return ActivityAggregateInput(
            sport_type=activity.sport_type,
            start_date_local=(activity.start_date_local or activity.start_date_utc).date(),
            distance_meters=activity.distance_meters,
            moving_time_seconds=activity.moving_time_seconds,
            total_elevation_gain_meters=activity.total_elevation_gain_meters,
            difficulty_score=activity.difficulty_score,
        )
