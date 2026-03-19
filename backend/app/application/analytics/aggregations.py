from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP


RUN_SPORT = "Run"
RIDE_SPORTS = {"Ride", "EBikeRide"}


def _quantize(value: Decimal, precision: str) -> Decimal:
    return value.quantize(Decimal(precision), rounding=ROUND_HALF_UP)


@dataclass(slots=True)
class ActivityAggregateInput:
    sport_type: str
    start_date_local: date
    distance_meters: Decimal
    moving_time_seconds: int
    total_elevation_gain_meters: Decimal | None
    heart_rate_drift_bpm: Decimal | None


@dataclass(slots=True)
class PeriodSummaryResult:
    sport_type: str
    period_type: str
    period_start: date
    activity_count: int
    total_distance_meters: Decimal
    total_moving_time_seconds: int
    average_speed_mps: Decimal | None
    average_pace_seconds_per_km: Decimal | None
    average_heart_rate_drift_bpm: Decimal | None
    total_elevation_gain_meters: Decimal | None


def _period_start(period_type: str, activity_date: date) -> date:
    if period_type == "week":
        return activity_date - timedelta(days=activity_date.weekday())
    if period_type == "month":
        return activity_date.replace(day=1)
    if period_type == "year":
        return activity_date.replace(month=1, day=1)
    raise ValueError(f"Unsupported period_type: {period_type}")


def aggregate_period_summaries(
    activities: list[ActivityAggregateInput],
    *,
    period_type: str,
) -> list[PeriodSummaryResult]:
    grouped: dict[tuple[str, date], list[ActivityAggregateInput]] = {}
    for activity in activities:
        key = (activity.sport_type, _period_start(period_type, activity.start_date_local))
        grouped.setdefault(key, []).append(activity)

    summaries: list[PeriodSummaryResult] = []
    for (sport_type, period_start), grouped_activities in grouped.items():
        total_distance = sum((activity.distance_meters for activity in grouped_activities), Decimal("0"))
        total_moving_time = sum(activity.moving_time_seconds for activity in grouped_activities)
        total_elevation = sum(
            (activity.total_elevation_gain_meters or Decimal("0") for activity in grouped_activities),
            Decimal("0"),
        )
        drift_values = [activity.heart_rate_drift_bpm for activity in grouped_activities if activity.heart_rate_drift_bpm is not None]
        average_speed_mps: Decimal | None = None
        average_pace_seconds_per_km: Decimal | None = None
        average_heart_rate_drift_bpm: Decimal | None = None
        if total_distance > 0 and total_moving_time > 0:
            if sport_type == RUN_SPORT:
                average_pace_seconds_per_km = _quantize(
                    (Decimal(total_moving_time) * Decimal("1000")) / total_distance,
                    "0.01",
                )
            elif sport_type in RIDE_SPORTS:
                average_speed_mps = _quantize(total_distance / Decimal(total_moving_time), "0.0001")
        if drift_values:
            average_heart_rate_drift_bpm = _quantize(sum(drift_values, Decimal("0")) / Decimal(len(drift_values)), "0.01")

        summaries.append(
            PeriodSummaryResult(
                sport_type=sport_type,
                period_type=period_type,
                period_start=period_start,
                activity_count=len(grouped_activities),
                total_distance_meters=_quantize(total_distance, "0.01"),
                total_moving_time_seconds=total_moving_time,
                average_speed_mps=average_speed_mps,
                average_pace_seconds_per_km=average_pace_seconds_per_km,
                average_heart_rate_drift_bpm=average_heart_rate_drift_bpm,
                total_elevation_gain_meters=_quantize(total_elevation, "0.01"),
            )
        )

    return sorted(summaries, key=lambda summary: (summary.sport_type, summary.period_start, summary.period_type))


def compare_periods(*, current: PeriodSummaryResult | None, previous: PeriodSummaryResult | None) -> dict:
    return {
        "current": current,
        "previous": previous,
        "delta_distance_meters": _delta_decimal(current.total_distance_meters if current else None, previous.total_distance_meters if previous else None),
        "delta_moving_time_seconds": _delta_int(current.total_moving_time_seconds if current else None, previous.total_moving_time_seconds if previous else None),
        "delta_activity_count": _delta_int(current.activity_count if current else None, previous.activity_count if previous else None),
        "delta_average_speed_mps": _delta_decimal(current.average_speed_mps if current else None, previous.average_speed_mps if previous else None),
        "delta_average_pace_seconds_per_km": _delta_decimal(current.average_pace_seconds_per_km if current else None, previous.average_pace_seconds_per_km if previous else None),
    }


def summarize_window(
    activities: list[ActivityAggregateInput],
    *,
    sport_type: str,
    window_type: str,
    window_start: date,
) -> PeriodSummaryResult | None:
    filtered = [activity for activity in activities if activity.sport_type == sport_type]
    if not filtered:
        return None

    total_distance = sum((activity.distance_meters for activity in filtered), Decimal("0"))
    total_moving_time = sum(activity.moving_time_seconds for activity in filtered)
    total_elevation = sum((activity.total_elevation_gain_meters or Decimal("0") for activity in filtered), Decimal("0"))
    drift_values = [activity.heart_rate_drift_bpm for activity in filtered if activity.heart_rate_drift_bpm is not None]
    average_speed_mps: Decimal | None = None
    average_pace_seconds_per_km: Decimal | None = None
    average_heart_rate_drift_bpm: Decimal | None = None
    if total_distance > 0 and total_moving_time > 0:
        if sport_type == RUN_SPORT:
            average_pace_seconds_per_km = _quantize(
                (Decimal(total_moving_time) * Decimal("1000")) / total_distance,
                "0.01",
            )
        elif sport_type in RIDE_SPORTS:
            average_speed_mps = _quantize(total_distance / Decimal(total_moving_time), "0.0001")
    if drift_values:
        average_heart_rate_drift_bpm = _quantize(sum(drift_values, Decimal("0")) / Decimal(len(drift_values)), "0.01")

    return PeriodSummaryResult(
        sport_type=sport_type,
        period_type=window_type,
        period_start=window_start,
        activity_count=len(filtered),
        total_distance_meters=_quantize(total_distance, "0.01"),
        total_moving_time_seconds=total_moving_time,
        average_speed_mps=average_speed_mps,
        average_pace_seconds_per_km=average_pace_seconds_per_km,
        average_heart_rate_drift_bpm=average_heart_rate_drift_bpm,
        total_elevation_gain_meters=_quantize(total_elevation, "0.01"),
    )


def _delta_decimal(current: Decimal | None, previous: Decimal | None) -> Decimal | None:
    if current is None and previous is None:
        return None
    return (current or Decimal("0")) - (previous or Decimal("0"))


def _delta_int(current: int | None, previous: int | None) -> int | None:
    if current is None and previous is None:
        return None
    return (current or 0) - (previous or 0)
