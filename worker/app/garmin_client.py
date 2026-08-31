from dataclasses import dataclass
from datetime import datetime
from typing import Any


class GarminActivityStreamNotFoundError(Exception):
    pass


class GarminAuthenticationError(Exception):
    pass


@dataclass(slots=True)
class GarminSession:
    client: Any

    def token_json(self) -> str:
        if hasattr(self.client, "client") and hasattr(self.client.client, "dumps"):
            return self.client.client.dumps()
        raise RuntimeError("Garmin client cannot serialize session tokens.")


class GarminApiClient:
    """Provider adapter returning the app's normalized activity/stream shapes."""

    def __init__(self, client_factory=None) -> None:
        self.client_factory = client_factory

    def _client(self, token_json: str):
        if self.client_factory:
            return self.client_factory(token_json)
        from garminconnect import Garmin  # type: ignore[import-not-found]
        client = Garmin()
        # garminconnect accepts the serialized token document directly as the
        # tokenstore argument and refreshes the DI access token automatically.
        client.login(token_json)
        return client

    def connect(self, token_json: str) -> GarminSession:
        try:
            return GarminSession(self._client(token_json))
        except Exception as exc:
            self._raise_authentication_error(exc)
            raise

    def get_activities(self, session: GarminSession, *, after: datetime | None = None) -> list[dict[str, Any]]:
        end = datetime.now().date()
        start = after.date() if after else datetime(2000, 1, 1).date()
        try:
            items = session.client.get_activities_by_date(
                start.isoformat(), end.isoformat(), sortorder="asc"
            )
        except Exception as exc:
            self._raise_authentication_error(exc)
            raise
        return [self.normalize_summary(item) for item in items]

    def get_activity_stream(self, session: GarminSession, activity_id: int) -> dict[str, Any]:
        try:
            details = session.client.get_activity_details(activity_id)
        except Exception as exc:
            self._raise_authentication_error(exc)
            raise
        try:
            from garminconnect.activity_details import parse_activity_detail_metrics  # type: ignore[import-not-found]
            samples = parse_activity_detail_metrics(details)
        except Exception:
            samples = details.get("metrics", []) if isinstance(details, dict) else []
        return self.normalize_stream(samples)

    @staticmethod
    def _raise_authentication_error(exc: Exception) -> None:
        current: BaseException | None = exc
        messages: list[str] = []
        while current is not None and len(messages) < 6:
            messages.append(f"{type(current).__name__}: {current}")
            current = current.__cause__ or current.__context__
        detail = " ".join(messages).lower()
        if "authentication" in detail or "401" in detail or "unauthorized" in detail:
            raise GarminAuthenticationError("Garmin session requires reauthentication.") from exc

    @staticmethod
    def normalize_summary(item: dict[str, Any]) -> dict[str, Any]:
        type_key = str(item.get("activityType", {}).get("typeKey", item.get("activityType", ""))).lower()
        if "e_bike" in type_key or "ebike" in type_key:
            sport = "EBikeRide"
        elif any(x in type_key for x in ("cycling", "biking", "bike")):
            sport = "Ride"
        elif "run" in type_key:
            sport = "Run"
        else:
            sport = None
        distance = item.get("distance", 0) or 0
        moving_time = _first_value(item, "movingDuration", "movingTime", "duration") or 0
        elapsed_time = _first_value(item, "elapsedDuration", "elapsedTime", "duration") or moving_time
        average_speed = _first_value(item, "averageMovingSpeed", "average_speed")
        if average_speed is None:
            average_speed = distance / moving_time if distance and moving_time else None
        return {"id": int(item["activityId"]), "name": item.get("activityName") or "Unnamed activity",
                "type": sport, "start_date": item.get("startTimeGMT") or item.get("startTimeLocal"),
                "start_date_local": item.get("startTimeLocal"), "distance": distance, "moving_time": moving_time,
                "elapsed_time": elapsed_time, "total_elevation_gain": item.get("elevationGain"),
                "average_speed": average_speed, "max_speed": item.get("maxSpeed"),
                "average_heartrate": item.get("averageHR"),
                "average_cadence": item.get("averageBikeCadence") or item.get("averageRunCadence")}

    @staticmethod
    def normalize_stream(samples: list[dict[str, Any]]) -> dict[str, dict[str, list[Any]]]:
        keys: dict[str, list[Any]] = {"time": [], "distance": [], "latlng": [], "altitude": [], "velocity_smooth": [],
                                      "heartrate": []}
        for sample in samples:
            keys["time"].append(
                _first_value(sample, "timerDuration", "elapsedTime", "sumDuration", "sumElapsedDuration",
                             "sumMovingDuration"))
            keys["distance"].append(_first_value(sample, "distance", "sumDistance", "directDistance"))
            lat = _first_value(sample, "latitude", "directLatitude")
            lon = _first_value(sample, "longitude", "directLongitude")
            keys["latlng"].append([lat, lon] if lat is not None and lon is not None else None)
            keys["altitude"].append(_first_value(sample, "elevation", "altitude", "directElevation", "directAltitude"))
            keys["velocity_smooth"].append(_first_value(sample, "speed", "directSpeed"))
            keys["heartrate"].append(_first_value(sample, "heartRate", "heartrate", "directHeartRate"))
        return {key: {"data": value} for key, value in keys.items() if any(item is not None for item in value)}


def _first_value(sample: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if sample.get(key) is not None:
            return sample[key]
    return None
