from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Strava Insights API"
    app_env: str = "local"
    service_name: str = "backend"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    backend_reload: bool = False
    database_url: str = "postgresql+psycopg://postgres:postgres@postgres:5432/strava_insights"
    redis_url: str = "redis://redis:6379/0"
    log_level: str = "INFO"
    session_secret_key: str = "change-me"
    session_cookie_name: str = "strava_insights_session"
    session_max_age_seconds: int = 60 * 60 * 24 * 14
    session_https_only: bool = False
    backend_public_url: str = "http://localhost:8000"
    frontend_public_url: str = "http://localhost:5173"
    strava_authorize_url: str = "https://www.strava.com/oauth/authorize"
    strava_token_url: str = "https://www.strava.com/oauth/token"
    strava_api_settings_url: str = "https://www.strava.com/settings/api"
    strava_scope: str = "read,activity:read_all"
    strava_oauth_state_ttl_seconds: int = 60 * 15

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @property
    def strava_redirect_uri(self) -> str:
        return f"{self.backend_public_url}/auth/strava/callback"


settings = Settings()
