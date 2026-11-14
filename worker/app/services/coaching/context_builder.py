"""Builds compact, data-only prompt contexts for activity coaching notes and period reviews."""

from datetime import date, datetime, timedelta
from typing import Any, Protocol

from app.services.coaching.contracts import ActivityEvaluation
from app.services.coaching.evidence import (
    build_evidence,
)
from app.services.coaching.hierarchy import HierarchyRepository, PeriodContextBuilder
from app.services.coaching.metrics import (
    format_duration,
    format_pace,
)
from app.services.coaching.periods import (
    PeriodContext,
    period_bounds,
    period_start_for,
    previous_period_start,
)

RECENT_ACTIVITIES = 7
RECENT_TOTALS_DAYS = 7


class CoachingReadRepository(HierarchyRepository, Protocol):
    def activity_evidence_batch(self, *, user_id: int, activities: list) -> dict: ...

    def get_activity(self, *, user_id: int, activity_id: int) -> Any | None: ...

    def get_stream(self, activity_id: int) -> Any | None: ...

    def get_splits(self, activity_id: int) -> Any | None: ...

    def get_threshold_profile(self, *, user_id: int, on_date: date) -> Any | None: ...

    def list_best_efforts(self, *, user_id: int, sport_type: str) -> list[Any]: ...

    def list_route_attempts(self, activity_id: int) -> list[Any]: ...

    def list_recent_activity_evaluations(
            self, *, user_id: int, before: datetime, limit: int
    ) -> list[ActivityEvaluation]: ...

    def recent_activity_totals(
            self, *, user_id: int, start: datetime, end: datetime
    ) -> dict: ...


class CoachingContextBuilder:
    def __init__(self, repository: CoachingReadRepository) -> None:
        self.repository = repository

    def build_activity_context(self, *, user_id: int, activity_id: int) -> dict | None:
        activity = self.repository.get_activity(
            user_id=user_id, activity_id=activity_id
        )
        if activity is None:
            return None
        local_start = activity.start_date_local or activity.start_date_utc
        profile = self.repository.get_threshold_profile(
            user_id=user_id, on_date=local_start.date()
        )
        recorded = (
            self.repository.get_splits(activity.id)
            if activity.source_provider == "garmin"
            else None
        )
        splits = []
        for lap in (
            recorded.laps if recorded is not None and recorded.status == "ready" else []
        ):
            row = {
                "split": lap["number"],
                "type": lap.get("lap_type"),
                "distance_km": round(lap["distance_meters"] / 1000, 3),
                "duration_seconds": _optional_precision(lap.get("duration_seconds"), 1),
                "avg_hr_bpm": lap.get("average_heartrate_bpm"),
            }
            if activity.sport_type == "Run":
                row["pace"] = format_pace(lap.get("average_pace_seconds_per_km"))
            else:
                row["speed_kph"] = _optional_precision(lap.get("average_speed_kph"), 1)
            splits.append(_drop_empty(row))

        evidence = self._evidence(user_id, [activity])[activity.id]
        terrain_by_lap = {row["lap"]: row for row in evidence["terrain"]["laps"]}
        for row in splits:
            terrain = terrain_by_lap.get(row["split"])
            if terrain and (
                    terrain["coverage_fraction"] > 0
                    or terrain["ascent_m"] is not None
                    or terrain["descent_m"] is not None
            ):
                row["terrain"] = {
                    key: terrain[key]
                    for key in (
                        "ascent_m",
                        "descent_m",
                        "net_change_m",
                        "net_grade_pct",
                        "coverage_fraction",
                        "elevation_totals_source",
                    )
                }

        band_time = evidence["hr_bands"]["coverage"]["classified_time_s"]
        zone_shares = (
            {
                f"{band}_percent": round(row["time_s"] * 100 / band_time, 1)
                for band, row in evidence["hr_bands"]["bands"].items()
            }
            if band_time
            else None
        )
        context: dict = {
            "activity": _drop_empty(
                {
                    **_activity_metrics(activity),
                    "elapsed_time": (
                        format_duration(activity.elapsed_time_seconds)
                        if activity.elapsed_time_seconds != activity.moving_time_seconds
                        else None
                    ),
                    "average_cadence": _optional_precision(activity.average_cadence, 1),
                    "athlete_notes": activity.description or None,
                }
            ),
            "athlete_thresholds": _thresholds(profile, activity.sport_type),
            "splits": splits,
            "activity_evidence": {"candidates": evidence["candidates"]},
            "terrain_context": {
                key: value
                for key, value in evidence["terrain"].items()
                if key not in {"laps", "total_ascent_m"}
            },
            "split_data_limitation": (
                None
                if splits
                else "Recorded Garmin laps are unavailable; within-activity pacing and HR changes cannot be assessed."
            ),
            "heart_rate_zones": zone_shares,
            "best_efforts": self._best_efforts(user_id, activity),
            "route_comparison": self._route_comparison(activity),
            "recent_training": self._recent_training(user_id, activity),
        }
        return _drop_empty(context)

    def build_period_context(
        self, *, user_id: int, period_type: str, period_start: date, today: date
    ) -> PeriodContext:
        return PeriodContextBuilder(self.repository).build(
            user_id=user_id,
            period_type=period_type,
            period_start=period_start,
            today=today,
        )

    def _evidence(self, user_id, activities):
        if hasattr(self.repository, "activity_evidence_batch"):
            return self.repository.activity_evidence_batch(
                user_id=user_id, activities=activities
            )
        return {
            activity.id: build_evidence(
                activity,
                self.repository.get_stream(activity.id),
                self.repository.get_splits(activity.id),
                self.repository.get_threshold_profile(
                    user_id=user_id, on_date=_local_date(activity)
                ),
            )
            for activity in activities
        }

    def _best_efforts(self, user_id: int, activity) -> list[dict]:
        ranks: dict[str, int] = {}
        results = []
        for effort in self.repository.list_best_efforts(
            user_id=user_id, sport_type=activity.sport_type
        ):
            rank = ranks.get(effort.effort_code, 0) + 1
            ranks[effort.effort_code] = rank
            if effort.activity_id == activity.id:
                results.append(
                    {
                        "distance": effort.effort_code,
                        "time": format_duration(effort.best_time_seconds),
                        "all_time_rank": rank,
                    }
                )
        return results

    def _route_comparison(self, activity) -> dict | None:
        attempts = self.repository.list_route_attempts(activity.id)
        if len(attempts) < 2:
            return None
        ids = [attempt.id for attempt in attempts]
        if activity.id not in ids:
            return None
        earlier = [
            attempt
            for attempt in attempts
            if attempt.id != activity.id
            and attempt.start_date_utc < activity.start_date_utc
        ]
        previous = max(
            earlier, key=lambda attempt: attempt.start_date_utc, default=None
        )
        return _drop_empty(
            {
                "attempts_on_this_route": len(attempts),
                "rank_by_moving_time": ids.index(activity.id) + 1,
                "this_time": format_duration(activity.moving_time_seconds),
                "best_time": format_duration(attempts[0].moving_time_seconds),
                "previous_attempt": (
                    None
                    if previous is None
                    else {
                        "date": _local_date(previous).isoformat(),
                        "time": format_duration(previous.moving_time_seconds),
                        "avg_hr_bpm": _optional_round(previous.average_heartrate_bpm),
                    }
                ),
            }
        )

    def _recent_training(self, user_id: int, activity) -> dict:
        local_start = activity.start_date_local or activity.start_date_utc
        recent = [
            ActivityEvaluation.model_validate(row)
            for row in self.repository.list_recent_activity_evaluations(
                user_id=user_id,
                before=local_start,
                limit=RECENT_ACTIVITIES,
            )
        ]
        return _drop_empty(
            {
                "previous_activities": [
                    {
                        "date": str(row.facts.date),
                        "sport": row.facts.sport,
                        "summary": row.summary,
                    }
                    for row in recent
                ],
                "days_since_previous_activity": (
                    (local_start.date() - recent[-1].facts.date).days
                    if recent
                    else None
                ),
                "totals_last_7_days_by_sport": self.repository.recent_activity_totals(
                    user_id=user_id,
                    start=local_start - timedelta(days=RECENT_TOTALS_DAYS),
                    end=local_start,
                ),
            }
        )


def _activity_metrics(activity) -> dict:
    local_day = _local_date(activity)
    metrics: dict = {
        "date": local_day.isoformat(),
        "sport": activity.sport_type,
        "name": activity.name,
        "distance_km": _optional_precision(activity.distance_km, 2)
        or round(float(activity.distance_meters or 0) / 1000, 2),
        "moving_time": format_duration(activity.moving_time_seconds),
        "elevation_gain_m": _optional_round(activity.total_elevation_gain_meters),
        "avg_hr_bpm": _optional_round(activity.average_heartrate_bpm),
    }
    if activity.sport_type == "Run":
        metrics["avg_pace"] = format_pace(
            _optional_float(activity.average_pace_seconds_per_km)
        )
    else:
        metrics["avg_speed_kph"] = _speed_kph(activity.average_speed_mps)
    return _drop_empty(metrics)


def _thresholds(profile, sport_type: str) -> dict | None:
    if profile is None:
        return None
    thresholds = {
        "aet_heart_rate_bpm": profile.aet_heart_rate_bpm,
        "ant_heart_rate_bpm": profile.ant_heart_rate_bpm,
    }
    if sport_type == "Run":
        thresholds["aet_pace"] = _pace_from_minutes(profile.aet_pace_min_per_km)
        thresholds["ant_pace"] = _pace_from_minutes(profile.ant_pace_min_per_km)
    return _drop_empty(thresholds) or None


def _local_date(activity) -> date:
    return (activity.start_date_local or activity.start_date_utc).date()


def _pace_from_minutes(value) -> str | None:
    minutes = _optional_float(value)
    return None if minutes is None else format_pace(minutes * 60)


def _speed_kph(speed_mps) -> float | None:
    value = _optional_float(speed_mps)
    return None if value is None else round(value * 3.6, 1)


def _optional_precision(value, digits: int) -> float | None:
    return None if value is None else round(float(value), digits)


def _optional_float(value) -> float | None:
    return None if value is None else float(value)


def _optional_round(value) -> int | None:
    return None if value is None else round(float(value))


def _drop_empty(values: dict) -> dict:
    return {key: value for key, value in values.items() if value not in (None, [], {})}
