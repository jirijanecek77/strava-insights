from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    service_name: str = "worker"
    redis_url: str = "redis://redis:6379/0"
    database_url: str = "postgresql+psycopg://postgres:postgres@postgres:5432/strava_insights"
    log_level: str = "INFO"
    session_secret_key: str = "change-me"
    strava_token_url: str = "https://www.strava.com/oauth/token"
    strava_api_base_url: str = "https://www.strava.com/api/v3"
    strava_activity_page_size: int = 100
    daily_sync_cron_hour_utc: int = 3
    daily_sync_cron_minute_utc: int = 0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
