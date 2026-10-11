"""Builds compact, data-only prompt contexts for activity coaching notes and period reviews."""

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Protocol

from app.services.coaching.metrics import (
    aerobic_decoupling_percent,
    compute_splits,
    format_duration,
    format_pace,
    heart_rate_zone_shares,
)
from app.services.coaching.prompts import PROMPT_VERSION

RECENT_ACTIVITY_DAYS = 14
RECENT_TOTALS_DAYS = 28


class CoachingReadRepository(Protocol):
    def get_activity(self, *, user_id: int, activity_id: int) -> Any | None: ...

    def get_stream(self, activity_id: int) -> Any | None: ...

    def get_threshold_profile(self, *, user_id: int, on_date: date) -> Any | None: ...

    def list_best_efforts(self, *, user_id: int, sport_type: str) -> list[Any]: ...

    def list_route_attempts(self, activity_id: int) -> list[Any]: ...

    def list_activities_with_notes(
        self, *, user_id: int, start: date | datetime, end: date | datetime
    ) -> list[tuple[Any, Any | None]]: ...


@dataclass(frozen=True, slots=True)
class PeriodContext:
    context: dict
    source_hash: str
    is_final: bool
    has_pending_notes: bool
    has_ready_notes: bool


def period_bounds(period_type: str, period_start: date) -> tuple[date, date]:
    """Return [start, end) of a week (Monday-based) or calendar month."""
    if period_type == "week":
        return period_start, period_start + timedelta(days=7)
    return period_start, _next_month(period_start)


def period_start_for(period_type: str, day: date) -> date:
    if period_type == "week":
        return day - timedelta(days=day.weekday())
    return day.replace(day=1)


def previous_period_start(period_type: str, period_start: date) -> date:
    if period_type == "week":
        return period_start - timedelta(days=7)
    return (period_start - timedelta(days=1)).replace(day=1)


class CoachingContextBuilder:
    def __init__(self, repository: CoachingReadRepository) -> None:
        self.repository = repository

    def build_activity_context(self, *, user_id: int, activity_id: int) -> dict | None:
        activity = self.repository.get_activity(user_id=user_id, activity_id=activity_id)
        if activity is None:
            return None
        local_start = activity.start_date_local or activity.start_date_utc
        stream = self.repository.get_stream(activity.id)
        profile = self.repository.get_threshold_profile(user_id=user_id, on_date=local_start.date())
        time_values = _stream_values(stream, "time_stream")
        distance_values = _stream_values(stream, "distance_stream")
        heart_rate_values = _stream_values(stream, "heartrate_stream")

        aet = _optional_float(getattr(profile, "aet_heart_rate_bpm", None))
        ant = _optional_float(getattr(profile, "ant_heart_rate_bpm", None))
        context: dict = {
            "activity": _drop_empty(
                {
                    **_activity_metrics(activity),
                    "start_time_local": local_start.strftime("%H:%M"),
                    "elapsed_time": format_duration(activity.elapsed_time_seconds),
                    "max_speed_kph": _speed_kph(activity.max_speed_mps),
                    "average_cadence": _optional_float(activity.average_cadence),
                    "athlete_notes": activity.description or None,
                }
            ),
            "athlete_thresholds": _thresholds(profile, activity.sport_type),
            "splits": compute_splits(
                sport_type=activity.sport_type,
                distance_meters=distance_values,
                time_seconds=time_values,
                heartrate_bpm=heart_rate_values,
                altitude_meters=_stream_values(stream, "altitude_stream"),
            ),
            "heart_rate_zones": heart_rate_zone_shares(
                time_seconds=time_values,
                heartrate_bpm=heart_rate_values,
                aet_heart_rate_bpm=aet,
                ant_heart_rate_bpm=ant,
            ),
            "aerobic_decoupling_percent": aerobic_decoupling_percent(
                distance_meters=distance_values,
                time_seconds=time_values,
                heartrate_bpm=heart_rate_values,
            ),
            "best_efforts": self._best_efforts(user_id, activity),
            "route_comparison": self._route_comparison(activity),
            "recent_training": self._recent_training(user_id, activity),
        }
        return _drop_empty(context)

    def build_period_context(
        self, *, user_id: int, period_type: str, period_start: date, today: date
    ) -> PeriodContext:
        start, end = period_bounds(period_type, period_start)
        rows = self.repository.list_activities_with_notes(user_id=user_id, start=start, end=end)
        previous_start, previous_end = period_bounds(
            period_type, previous_period_start(period_type, period_start)
        )
        previous_rows = self.repository.list_activities_with_notes(
            user_id=user_id, start=previous_start, end=previous_end
        )
        activities = [
            {
                **_activity_metrics(activity),
                "coaching_summary": _ready_summary(note),
            }
            for activity, note in rows
        ]
        context = {
            "period_type": period_type,
            "period_start": start.isoformat(),
            "period_end": (end - timedelta(days=1)).isoformat(),
            "in_progress": end > today,
            "totals_by_sport": _totals_by_sport(activity for activity, _ in rows),
            "previous_period_totals_by_sport": _totals_by_sport(
                activity for activity, _ in previous_rows
            ),
            "activities": activities,
        }
        hash_input = [
            PROMPT_VERSION,
            period_type,
            start.isoformat(),
            [
                [activity.id, str(activity.distance_meters), activity.moving_time_seconds, _ready_summary(note)]
                for activity, note in rows
            ],
        ]
        return PeriodContext(
            context=context,
            source_hash=hashlib.sha256(json.dumps(hash_input).encode()).hexdigest(),
            is_final=end <= today,
            has_pending_notes=any(
                note is not None and note.status in {"pending", "generating"} for _, note in rows
            ),
            has_ready_notes=any(_ready_summary(note) is not None for _, note in rows),
        )

    def _best_efforts(self, user_id: int, activity) -> list[dict]:
        ranks: dict[str, int] = {}
        results = []
        for effort in self.repository.list_best_efforts(user_id=user_id, sport_type=activity.sport_type):
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
            if attempt.id != activity.id and attempt.start_date_utc < activity.start_date_utc
        ]
        previous = max(earlier, key=lambda attempt: attempt.start_date_utc, default=None)
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
        rows = [
            (other, note)
            for other, note in self.repository.list_activities_with_notes(
                user_id=user_id,
                start=local_start - timedelta(days=RECENT_TOTALS_DAYS),
                end=local_start,
            )
            if other.id != activity.id
        ]
        recent_cutoff = local_start - timedelta(days=RECENT_ACTIVITY_DAYS)
        recent = [
            {**_activity_metrics(other), "coaching_summary": _ready_summary(note)}
            for other, note in rows
            if (other.start_date_local or other.start_date_utc) >= recent_cutoff
        ]
        previous = rows[-1][0] if rows else None
        return _drop_empty(
            {
                "days_since_previous_activity": (
                    None
                    if previous is None
                    else (local_start.date() - _local_date(previous)).days
                ),
                f"activities_last_{RECENT_ACTIVITY_DAYS}_days": recent,
                f"totals_last_{RECENT_TOTALS_DAYS}_days_by_sport": _totals_by_sport(
                    other for other, _ in rows
                ),
            }
        )


def _activity_metrics(activity) -> dict:
    local_day = _local_date(activity)
    metrics: dict = {
        "date": local_day.isoformat(),
        "weekday": local_day.strftime("%A"),
        "sport": activity.sport_type,
        "name": activity.name,
        "distance_km": _optional_float(activity.distance_km)
        or round(float(activity.distance_meters or 0) / 1000, 2),
        "moving_time": format_duration(activity.moving_time_seconds),
        "elevation_gain_m": _optional_round(activity.total_elevation_gain_meters),
        "avg_hr_bpm": _optional_round(activity.average_heartrate_bpm),
    }
    if activity.sport_type == "Run":
        metrics["avg_pace"] = format_pace(_optional_float(activity.average_pace_seconds_per_km))
    else:
        metrics["avg_speed_kph"] = _speed_kph(activity.average_speed_mps)
    return _drop_empty(metrics)


def _totals_by_sport(activities) -> dict:
    totals: dict[str, dict] = {}
    for activity in activities:
        sport = totals.setdefault(
            activity.sport_type,
            {"activities": 0, "distance_m": 0.0, "moving_time_s": 0, "elevation_gain_m": 0.0},
        )
        sport["activities"] += 1
        sport["distance_m"] += float(activity.distance_meters or 0)
        sport["moving_time_s"] += int(activity.moving_time_seconds or 0)
        sport["elevation_gain_m"] += float(activity.total_elevation_gain_meters or 0)
    return {
        sport_type: {
            "activities": values["activities"],
            "distance_km": round(values["distance_m"] / 1000, 1),
            "moving_time": format_duration(values["moving_time_s"]),
            "elevation_gain_m": round(values["elevation_gain_m"]),
        }
        for sport_type, values in sorted(totals.items())
    }


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


def _ready_summary(note) -> str | None:
    if note is None or note.status != "ready":
        return None
    return note.summary


def _stream_values(stream, attribute: str) -> list:
    payload = getattr(stream, attribute, None) if stream is not None else None
    return list((payload or {}).get("data", []) or [])


def _local_date(activity) -> date:
    return (activity.start_date_local or activity.start_date_utc).date()


def _pace_from_minutes(value) -> str | None:
    minutes = _optional_float(value)
    return None if minutes is None else format_pace(minutes * 60)


def _speed_kph(speed_mps) -> float | None:
    value = _optional_float(speed_mps)
    return None if value is None else round(value * 3.6, 1)


def _optional_float(value) -> float | None:
    return None if value is None else float(value)


def _optional_round(value) -> int | None:
    return None if value is None else round(float(value))


def _drop_empty(values: dict) -> dict:
    return {key: value for key, value in values.items() if value not in (None, [], {})}


def _next_month(day: date) -> date:
    return (day.replace(day=28) + timedelta(days=4)).replace(day=1)
