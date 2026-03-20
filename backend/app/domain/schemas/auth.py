from pydantic import BaseModel, model_validator


class StravaCredentialStateResponse(BaseModel):
    client_id: str | None = None
    has_saved_secret: bool
    can_connect: bool
    strava_api_settings_url: str


class StartStravaLoginRequest(BaseModel):
    client_id: str | None = None
    client_secret: str | None = None
    use_saved_credentials: bool = False

    @model_validator(mode="after")
    def validate_mode(self) -> "StartStravaLoginRequest":
        has_manual_credentials = bool((self.client_id or "").strip()) and bool((self.client_secret or "").strip())
        if self.use_saved_credentials == has_manual_credentials:
            raise ValueError("Provide either saved credentials or both client_id and client_secret.")
        return self


class StartStravaLoginResponse(BaseModel):
    authorization_url: str
