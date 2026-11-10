from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from zoneinfo import ZoneInfo


class Settings(BaseSettings):
    app_env: str = "local"
    service_name: str = "worker"
    redis_url: str = "redis://redis:6379/0"
    database_url: str = (
        "postgresql+psycopg://postgres:postgres@postgres:5432/strava_insights"
    )
    log_level: str = "INFO"
    session_secret_key: str = "change-me"
    daily_sync_cron_hour_utc: int = 3
    daily_sync_cron_minute_utc: int = 0
    sync_dispatch_poll_interval_seconds: int = 2
    llm_api_key: str = ""
    llm_model: str = "openai/gpt-oss-120b"
    llm_timeout_seconds: float = 120.0
    coaching_batch_size: int = 5
    coaching_poll_interval_minutes: int = 15
    planning_timezone: str = "Europe/Prague"

    @field_validator("planning_timezone")
    @classmethod
    def validate_planning_timezone(cls, value: str) -> str:
        ZoneInfo(value)
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
