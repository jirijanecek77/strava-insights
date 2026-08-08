from pydantic import BaseModel, model_validator


class IntervalsCredentialStateResponse(BaseModel):
    athlete_id: str | None = None
    has_saved_secret: bool
    can_connect: bool
    intervals_settings_url: str


class StartIntervalsLoginRequest(BaseModel):
    athlete_id: str | None = None
    api_key: str | None = None
    use_saved_credentials: bool = False

    @model_validator(mode="after")
    def validate_mode(self) -> "StartIntervalsLoginRequest":
        has_manual_credentials = bool((self.athlete_id or "").strip()) and bool((self.api_key or "").strip())
        if self.use_saved_credentials == has_manual_credentials:
            raise ValueError("Provide either saved credentials or both athlete_id and api_key.")
        return self


class StartIntervalsLoginResponse(BaseModel):
    user_id: int
    is_new_user: bool
