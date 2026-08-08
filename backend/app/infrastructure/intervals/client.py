from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings


@dataclass(slots=True)
class IntervalsAthleteProfile:
    athlete_id: int
    display_name: str
    profile_picture_url: str | None = None


class IntervalsAuthClient:
    def __init__(self) -> None:
        self.base_url = settings.intervals_api_base_url.rstrip("/")

    def get_athlete_profile(self, *, athlete_id: str, api_key: str) -> IntervalsAthleteProfile:
        intervals_athlete_id = format_intervals_athlete_id(athlete_id)
        response = httpx.get(
            f"{self.base_url}/athlete/{intervals_athlete_id}",
            auth=("API_KEY", api_key),
            timeout=30.0,
        )
        response.raise_for_status()
        payload = response.json()
        return self._build_profile(payload, fallback_athlete_id=intervals_athlete_id)

    @staticmethod
    def _build_profile(payload: dict[str, Any], *, fallback_athlete_id: str) -> IntervalsAthleteProfile:
        raw_id = payload.get("id") or payload.get("athlete_id") or fallback_athlete_id
        athlete_id = _parse_athlete_id(raw_id)
        display_name = (
            payload.get("name")
            or payload.get("athlete_name")
            or " ".join(part for part in [payload.get("firstname"), payload.get("lastname")] if part)
            or f"Intervals athlete {athlete_id}"
        )
        return IntervalsAthleteProfile(
            athlete_id=athlete_id,
            display_name=display_name,
            profile_picture_url=payload.get("profile") or payload.get("profile_picture_url") or payload.get("avatar_url"),
        )


def _parse_athlete_id(value: Any) -> int:
    text = str(value).strip()
    if text.startswith("i") and text[1:].isdigit():
        text = text[1:]
    if not text.isdigit():
        raise ValueError(f"Intervals athlete id must be numeric or i-prefixed numeric, got {value!r}.")
    return int(text)


def format_intervals_athlete_id(value: Any) -> str:
    return f"i{_parse_athlete_id(value)}"
