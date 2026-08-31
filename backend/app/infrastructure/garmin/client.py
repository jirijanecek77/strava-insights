"""Small adapter around garminconnect; no Garmin objects cross the app boundary."""

from dataclasses import dataclass
from typing import Any, Callable, NoReturn


class GarminLoginError(Exception):
    pass


class GarminRateLimitError(GarminLoginError):
    pass


class GarminTemporaryError(GarminLoginError):
    pass


@dataclass(slots=True)
class GarminProfile:
    external_user_id: str
    display_name: str
    profile_picture_url: str | None = None


class GarminAuthClient:
    def __init__(self, factory: Callable[..., Any] | None = None) -> None:
        self._factory = factory

    def _new(self, email: str | None = None, password: str | None = None) -> Any:
        if self._factory is None:
            from garminconnect import Garmin  # type: ignore[import-not-found]

            self._factory = Garmin
        if email is None and password is None:
            return self._factory()
        return self._factory(email=email, password=password)

    def login(self, email: str, password: str) -> tuple[Any, GarminProfile]:
        try:
            client = self._new(email, password)
            result = client.login()
            if result is False:
                raise GarminLoginError("Garmin login was rejected.")
            return client, self.profile(client)
        except GarminLoginError:
            raise
        except Exception as exc:
            self._raise_mapped_login_error(exc)

    @staticmethod
    def _raise_mapped_login_error(exc: Exception) -> NoReturn:
        name = type(exc).__name__
        chain_text = GarminAuthClient._exception_chain_text(exc).lower()
        if "429" in chain_text or "rate limited" in chain_text or "rate limit" in chain_text:
            raise GarminRateLimitError("Garmin login is temporarily rate limited.") from exc
        if "unexpected title" in chain_text or "cloudflare" in chain_text or "bot challenge" in chain_text:
            raise GarminTemporaryError("Garmin is temporarily unavailable.") from exc
        if name == "GarminConnectAuthenticationError":
            raise GarminLoginError("Garmin login failed.") from exc
        if name == "GarminConnectTooManyRequestsError":
            raise GarminRateLimitError("Garmin login is temporarily rate limited.") from exc
        if name == "GarminConnectConnectionError":
            raise GarminTemporaryError("Garmin is temporarily unavailable.") from exc
        raise GarminLoginError("Garmin login failed.") from exc

    @staticmethod
    def _exception_chain_text(exc: BaseException) -> str:
        messages: list[str] = []
        current: BaseException | None = exc
        while current is not None and len(messages) < 8:
            messages.append(str(current))
            current = current.__cause__ or current.__context__
        return " ".join(messages)

    @staticmethod
    def profile(client: Any) -> GarminProfile:
        raw = client.get_full_name() if hasattr(client, "get_full_name") else None
        display_name = raw or getattr(client, "display_name", None) or "Garmin athlete"
        external_id = str(getattr(client, "display_name", None) or getattr(client, "username", "unknown"))
        return GarminProfile(external_id, display_name)

    @staticmethod
    def token_json(client: Any) -> str:
        if hasattr(client, "client") and hasattr(client.client, "dumps"):
            return client.client.dumps()
        raise GarminLoginError("Garmin client cannot serialize its session tokens.")

    def reconnect(self, token_json: str) -> tuple[Any, GarminProfile]:
        """Reconnect using encrypted token material without retaining a password."""
        try:
            client = self._new()
            client.login(tokenstore=token_json)
            return client, self.profile(client)
        except Exception as exc:
            raise GarminLoginError("Saved Garmin session expired.") from exc
