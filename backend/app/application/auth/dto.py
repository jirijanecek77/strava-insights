from dataclasses import dataclass


@dataclass(slots=True)
class GarminCredentials:
    email: str
    password: str | None = None
    token_json: str | None = None


@dataclass(slots=True)
class AuthenticatedUser:
    id: int
    external_user_id: str
    display_name: str
    profile_picture_url: str | None
    is_new_user: bool = False
