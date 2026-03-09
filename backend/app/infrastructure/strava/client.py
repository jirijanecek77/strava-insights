from datetime import UTC, datetime

import httpx

from app.application.auth.dto import StravaTokenPayload
from app.core.config import settings


class StravaAuthClient:
    def exchange_code_for_token(self, code: str) -> StravaTokenPayload:
        response = httpx.post(
            settings.strava_token_url,
            data=self._build_token_request_data(code=code, grant_type="authorization_code"),
            timeout=30.0,
        )
        response.raise_for_status()
        return self._build_token_payload(response.json())

    def refresh_access_token(self, refresh_token: str) -> StravaTokenPayload:
        response = httpx.post(
            settings.strava_token_url,
            data=self._build_token_request_data(refresh_token=refresh_token, grant_type="refresh_token"),
            timeout=30.0,
        )
        response.raise_for_status()
        return self._build_token_payload(response.json())

    def _build_token_request_data(
        self,
        *,
        grant_type: str,
        code: str | None = None,
        refresh_token: str | None = None,
    ) -> dict[str, str]:
        data = {
            "client_id": settings.strava_client_id,
            "client_secret": settings.strava_client_secret,
            "grant_type": grant_type,
        }
        if code is not None:
            data["code"] = code
        if refresh_token is not None:
            data["refresh_token"] = refresh_token
        return data

    def _build_token_payload(self, payload: dict) -> StravaTokenPayload:
        athlete = payload["athlete"]

        return StravaTokenPayload(
            access_token=payload["access_token"],
            refresh_token=payload["refresh_token"],
            expires_at=datetime.fromtimestamp(payload["expires_at"], tz=UTC),
            scope=payload.get("scope"),
            athlete_id=athlete["id"],
            athlete_firstname=athlete.get("firstname"),
            athlete_lastname=athlete.get("lastname"),
            athlete_profile=athlete.get("profile"),
        )
