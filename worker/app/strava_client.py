from datetime import UTC, datetime
from typing import Any

import httpx

from app.config import settings


class StravaActivityStreamNotFoundError(Exception):
    def __init__(self, activity_id: int) -> None:
        super().__init__(f"Strava activity stream not found for activity {activity_id}.")
        self.activity_id = activity_id


class StravaApiClient:
    def __init__(self) -> None:
        self.base_url = settings.strava_api_base_url.rstrip("/")

    def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        response = httpx.post(
            settings.strava_token_url,
            data={
                "client_id": settings.strava_client_id,
                "client_secret": settings.strava_client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()

    def get_activities(self, access_token: str, *, after: datetime | None = None) -> list[dict[str, Any]]:
        headers = {"Authorization": f"Bearer {access_token}"}
        page = 1
        all_activities: list[dict[str, Any]] = []

        while True:
            params: dict[str, Any] = {
                "page": page,
                "per_page": settings.strava_activity_page_size,
            }
            if after is not None:
                params["after"] = int(after.timestamp())
            response = httpx.get(
                f"{self.base_url}/athlete/activities",
                headers=headers,
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            payload = response.json()
            if not payload:
                break
            all_activities.extend(payload)
            if len(payload) < settings.strava_activity_page_size:
                break
            page += 1

        return all_activities

    def get_activity_stream(self, access_token: str, activity_id: int) -> dict[str, Any]:
        response = httpx.get(
            f"{self.base_url}/activities/{activity_id}/streams",
            headers={"Authorization": f"Bearer {access_token}"},
            params={
                "keys": "time,heartrate,latlng,altitude,velocity_smooth,distance",
                "key_by_type": "true",
            },
            timeout=30.0,
        )
        if response.status_code == 404:
            raise StravaActivityStreamNotFoundError(activity_id)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def parse_expires_at(payload: dict[str, Any]) -> datetime:
        return datetime.fromtimestamp(payload["expires_at"], tz=UTC)
