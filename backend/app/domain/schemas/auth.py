from pydantic import BaseModel, model_validator


class GarminCredentialStateResponse(BaseModel):
    external_user_id: str | None = None
    has_saved_secret: bool
    can_connect: bool
    provider: str = "garmin"


class StartGarminLoginRequest(BaseModel):
    email: str | None = None
    password: str | None = None
    use_saved_credentials: bool = False

    @model_validator(mode="after")
    def validate_mode(self) -> "StartGarminLoginRequest":
        has_manual_credentials = bool((self.email or "").strip()) and bool((self.password or "").strip())
        if self.use_saved_credentials == has_manual_credentials:
            raise ValueError(
                "Provide either saved credentials or both email and password."
            )
        return self


class StartGarminLoginResponse(BaseModel):
    user_id: int
    is_new_user: bool
