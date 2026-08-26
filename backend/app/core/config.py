from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Garmin Insights API"
    app_env: str = "local"
    service_name: str = "backend"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    backend_reload: bool = False
    database_url: str = (
        "postgresql+psycopg://postgres:postgres@postgres:5432/strava_insights"
    )
    redis_url: str = "redis://redis:6379/0"
    log_level: str = "INFO"
    session_secret_key: str = "change-me"
    session_cookie_name: str = "garmin_insights_session"
    session_max_age_seconds: int = 60 * 60 * 24 * 14
    session_https_only: bool = False
    backend_public_url: str = "http://localhost:8000"
    frontend_public_url: str = "http://localhost:5173"
    admin_external_user_id: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @property
    def effective_admin_external_user_id(self) -> str:
        return self.admin_external_user_id or "68c0e5b9-3370-4e83-904b-de6edcf24551"


settings = Settings()
