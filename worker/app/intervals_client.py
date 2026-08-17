from datetime import UTC, datetime
from typing import Any

import httpx

from app.config import settings


class IntervalsActivityStreamNotFoundError(Exception):
    def __init__(self, activity_id: int) -> None:
        super().__init__(
            f"Intervals.icu activity stream not found for activity {activity_id}."
        )
        self.activity_id = activity_id


class IntervalsApiClient:
    def __init__(self) -> None:
        self.base_url = settings.intervals_api_base_url.rstrip("/")

    def get_activities(
        self, athlete_id: str, api_key: str, *, after: datetime | None = None
    ) -> list[dict[str, Any]]:
        intervals_athlete_id = self.format_athlete_id(athlete_id)
        params: dict[str, Any] = {
            "oldest": self._oldest_date(after),
            "newest": datetime.now(UTC).date().isoformat(),
        }
        response = httpx.get(
            f"{self.base_url}/athlete/{intervals_athlete_id}/activities",
            auth=("API_KEY", api_key),
            params=params,
            timeout=60.0,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("Intervals.icu activities response must be a list.")
        return payload

    def get_run_pace_curves(
        self,
        athlete_id: str,
        api_key: str,
        *,
        distances_meters: list[float],
    ) -> dict[str, Any]:
        intervals_athlete_id = self.format_athlete_id(athlete_id)
        response = httpx.get(
            f"{self.base_url}/athlete/{intervals_athlete_id}/activity-pace-curves",
            auth=("API_KEY", api_key),
            params={
                "oldest": "1970-01-01",
                "newest": datetime.now(UTC).date().isoformat(),
                "type": "Run",
                "distances": ",".join(str(distance) for distance in distances_meters),
            },
            timeout=60.0,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("curves"), list):
            raise ValueError(
                "Intervals.icu pace curves response must contain a curves list."
            )
        return payload

    def get_activity_stream(self, api_key: str, activity_id: int) -> dict[str, Any]:
        response = httpx.get(
            f"{self.base_url}/activity/i{activity_id}/streams.json",
            auth=("API_KEY", api_key),
            timeout=60.0,
        )
        if response.status_code == 404:
            raise IntervalsActivityStreamNotFoundError(activity_id)
        response.raise_for_status()
        return self._normalize_stream_payload(response.json())

    @staticmethod
    def parse_activity_id(value: Any) -> int:
        text = str(value).strip()
        if text.startswith("i") and text[1:].isdigit():
            text = text[1:]
        if not text.isdigit():
            raise ValueError(
                f"Intervals.icu activity id must be numeric or i-prefixed numeric, got {value!r}."
            )
        return int(text)

    @staticmethod
    def format_athlete_id(value: Any) -> str:
        text = str(value).strip()
        if text.startswith("i") and text[1:].isdigit():
            text = text[1:]
        if not text.isdigit():
            raise ValueError(
                f"Intervals.icu athlete id must be numeric or i-prefixed numeric, got {value!r}."
            )
        return f"i{text}"

    @staticmethod
    def _oldest_date(after: datetime | None) -> str:
        if after is None:
            return "1970-01-01"
        return after.astimezone(UTC).date().isoformat()

    @classmethod
    def _normalize_stream_payload(cls, payload: Any) -> dict[str, Any]:
        if isinstance(payload, dict):
            return {
                cls._normalize_stream_key(key): cls._as_stream(
                    cls._normalize_stream_key(key), value
                )
                for key, value in payload.items()
            }
        if isinstance(payload, list):
            normalized: dict[str, Any] = {}
            for item in payload:
                if not isinstance(item, dict):
                    continue
                key = item.get("type") or item.get("name")
                if key is None:
                    continue
                normalized_key = cls._normalize_stream_key(str(key))
                normalized[normalized_key] = cls._as_stream(normalized_key, item)
            return normalized
        raise ValueError(
            "Intervals.icu activity stream response must be an object or list."
        )

    @classmethod
    def _as_stream(cls, key: str, value: Any) -> dict[str, Any]:
        if key == "latlng" and isinstance(value, dict) and "data2" in value:
            return {
                "data": cls._latlng_pairs(value.get("data", []), value.get("data2", []))
            }
        if isinstance(value, dict) and "data" in value:
            return value
        if isinstance(value, dict) and "values" in value:
            return {"data": value["values"]}
        return {"data": value if isinstance(value, list) else []}

    @staticmethod
    def _latlng_pairs(latitudes: Any, longitudes: Any) -> list[list[float] | None]:
        if not isinstance(latitudes, list) or not isinstance(longitudes, list):
            return []
        pairs: list[list[float] | None] = []
        for index, latitude in enumerate(latitudes):
            longitude = longitudes[index] if index < len(longitudes) else None
            if latitude is None or longitude is None:
                pairs.append(None)
                continue
            pairs.append([float(latitude), float(longitude)])
        return pairs

    @staticmethod
    def _normalize_stream_key(key: str) -> str:
        aliases = {
            "latlng": "latlng",
            "latlngs": "latlng",
            "lat_lng": "latlng",
            "location": "latlng",
            "altitude": "altitude",
            "alt": "altitude",
            "heartrate": "heartrate",
            "hr": "heartrate",
            "heart_rate": "heartrate",
            "velocity_smooth": "velocity_smooth",
            "velocity": "velocity_smooth",
            "speed": "velocity_smooth",
            "distance": "distance",
            "time": "time",
        }
        return aliases.get(key, key)
