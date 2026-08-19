from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, NoReturn

from app.models import Activity, ActivityStream
from app.repositories import ActivityRepository, ActivityStreamRepository
from app.services.activity_summary import (
    distance_km,
    format_moving_time,
    format_pace,
    pace_seconds_per_km,
    speed_kph,
    summary_metric_display,
)
from app.services.stream_sanitizer import sanitize_stream_payload


class ActivityImportWriter:
    def __init__(
        self,
        *,
        activities: ActivityRepository,
        activity_streams: ActivityStreamRepository,
    ) -> None:
        self.activities = activities
        self.activity_streams = activity_streams

    def upsert_activity(self, *, user_id: int, payload: dict[str, Any]) -> Activity:
        start_date_utc = self._required_datetime(
            self._parse_datetime(
                self._first_present(
                    payload, "start_date", "start_date_utc", "start_date_local"
                )
            )
        )
        activity = self.activities.get_by_source_activity_id(user_id, payload["id"])
        if activity is None:
            activity = Activity(
                user_id=user_id,
                strava_activity_id=payload["id"],
                name=payload.get("name") or "Unnamed activity",
                sport_type=payload["type"],
                start_date_utc=start_date_utc,
            )
        activity.description = payload.get("description")
        activity.sport_type = payload["type"]
        activity.name = payload.get("name") or activity.name
        activity.start_date_utc = start_date_utc
        activity.start_date_local = self._parse_datetime(
            payload.get("start_date_local") or payload.get("start_date")
        )
        activity.distance_meters = Decimal(
            str(self._first_present(payload, "distance", "distance_meters") or 0)
        )
        activity.moving_time_seconds = int(
            self._first_present(payload, "moving_time", "moving_time_seconds") or 0
        )
        activity.elapsed_time_seconds = (
            self._first_present(payload, "elapsed_time", "elapsed_time_seconds")
            or activity.moving_time_seconds
        )
        activity.total_elevation_gain_meters = self._decimal_or_none(
            self._first_present(
                payload, "total_elevation_gain", "total_elevation_gain_meters"
            )
        )
        activity.average_speed_mps = self._decimal_or_none(
            self._first_present(payload, "average_speed", "avg_speed"), scale=4
        )
        activity.average_speed_kph = speed_kph(activity.average_speed_mps)
        activity.max_speed_mps = self._decimal_or_none(
            self._first_present(payload, "max_speed", "max_speed_mps"), scale=4
        )
        activity.average_heartrate_bpm = self._decimal_or_none(
            self._first_present(payload, "average_heartrate", "avg_hr", "average_hr")
        )
        activity.average_cadence = self._decimal_or_none(
            self._first_present(payload, "average_cadence", "avg_cadence")
        )
        activity.distance_km = distance_km(activity.distance_meters)
        activity.moving_time_display = format_moving_time(activity.moving_time_seconds)
        activity.average_pace_seconds_per_km = pace_seconds_per_km(
            activity.distance_meters,
            activity.moving_time_seconds,
            activity.sport_type,
        )
        activity.average_pace_display = format_pace(
            activity.average_pace_seconds_per_km
        )
        activity.summary_metric_display = summary_metric_display(
            activity.sport_type,
            pace_display=activity.average_pace_display,
            speed_kph_value=activity.average_speed_kph,
        )
        return self.activities.save(activity)

    def upsert_stream(
        self, *, activity: Activity, payload: dict[str, Any]
    ) -> ActivityStream:
        sanitized = sanitize_stream_payload(payload, activity.sport_type)
        activity_stream = self.activity_streams.get_by_activity_id(activity.id)
        if activity_stream is None:
            activity_stream = ActivityStream(activity_id=activity.id)
        activity_stream.time_stream = sanitized.get("time")
        activity_stream.distance_stream = sanitized.get("distance")
        activity_stream.latlng_stream = sanitized.get("latlng")
        activity_stream.altitude_stream = sanitized.get("altitude")
        activity_stream.velocity_smooth_stream = sanitized.get("velocity_smooth")
        activity_stream.heartrate_stream = sanitized.get("heartrate")
        speed_values = [
            value
            for value in (activity_stream.velocity_smooth_stream or {}).get("data", [])
            if isinstance(value, int | float) and not isinstance(value, bool)
        ]
        if speed_values:
            activity.max_speed_mps = self._decimal_or_none(max(speed_values), scale=4)
        return self.activity_streams.save(activity_stream)

    @staticmethod
    def parse_datetime(value: str | None) -> datetime | None:
        return ActivityImportWriter._parse_datetime(value)

    @staticmethod
    def decimal_or_none(value: float | int | None, *, scale: int = 2) -> Decimal | None:
        return ActivityImportWriter._decimal_or_none(value, scale=scale)

    @staticmethod
    def first_present(payload: dict[str, Any], *keys: str) -> Any:
        return ActivityImportWriter._first_present(payload, *keys)

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        if value is None:
            return None
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed

    @staticmethod
    def _required_datetime(value: datetime | None) -> datetime:
        if value is None:
            ActivityImportWriter._raise_missing_start_date()
        return value

    @staticmethod
    def _raise_missing_start_date() -> NoReturn:
        raise ValueError("Imported activity is missing a start date.")

    @staticmethod
    def _decimal_or_none(
        value: float | int | None, *, scale: int = 2
    ) -> Decimal | None:
        if value is None:
            return None
        quantize_value = "0." + ("0" * (scale - 1)) + "1"
        return Decimal(str(value)).quantize(Decimal(quantize_value))

    @staticmethod
    def _first_present(payload: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if payload.get(key) is not None:
                return payload[key]
        return None
