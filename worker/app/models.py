from datetime import date, datetime

from sqlalchemy import JSON, BigInteger, DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    birthday: Mapped[date | None]
    speed_max: Mapped[float | None] = mapped_column(Numeric(5, 2))
    max_heart_rate_override: Mapped[int | None]


class SyncJob(Base):
    __tablename__ = "sync_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    sync_type: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    progress_total: Mapped[int | None]
    progress_completed: Mapped[int | None]
    error_message: Mapped[str | None]
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class OauthToken(Base):
    __tablename__ = "oauth_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    access_token_encrypted: Mapped[str] = mapped_column(String(2048), nullable=False)
    refresh_token_encrypted: Mapped[str] = mapped_column(String(2048), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scope: Mapped[str | None] = mapped_column(String(255))
    strava_athlete_id: Mapped[int | None] = mapped_column(BigInteger)


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    strava_activity_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None]
    sport_type: Mapped[str] = mapped_column(String(50), nullable=False)
    start_date_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    start_date_local: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    distance_meters: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    distance_km: Mapped[float | None] = mapped_column(Numeric(10, 2))
    moving_time_seconds: Mapped[int] = mapped_column(nullable=False)
    moving_time_display: Mapped[str | None] = mapped_column(String(32))
    elapsed_time_seconds: Mapped[int | None]
    total_elevation_gain_meters: Mapped[float | None] = mapped_column(Numeric(10, 2))
    elev_high_meters: Mapped[float | None] = mapped_column(Numeric(10, 2))
    elev_low_meters: Mapped[float | None] = mapped_column(Numeric(10, 2))
    average_speed_mps: Mapped[float | None] = mapped_column(Numeric(10, 4))
    average_speed_kph: Mapped[float | None] = mapped_column(Numeric(10, 2))
    max_speed_mps: Mapped[float | None] = mapped_column(Numeric(10, 4))
    average_heartrate_bpm: Mapped[float | None] = mapped_column(Numeric(6, 2))
    max_heartrate_bpm: Mapped[int | None]
    average_cadence: Mapped[float | None] = mapped_column(Numeric(6, 2))
    average_pace_seconds_per_km: Mapped[float | None] = mapped_column(Numeric(10, 2))
    average_pace_display: Mapped[str | None] = mapped_column(String(16))
    summary_metric_display: Mapped[str | None] = mapped_column(String(32))
    difficulty_score: Mapped[float | None] = mapped_column(Numeric(12, 4))
    start_latlng: Mapped[dict | None] = mapped_column(JSON)


class ActivityStream(Base):
    __tablename__ = "activity_streams"

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    time_stream: Mapped[dict | None] = mapped_column(JSON)
    distance_stream: Mapped[dict | None] = mapped_column(JSON)
    latlng_stream: Mapped[dict | None] = mapped_column(JSON)
    altitude_stream: Mapped[dict | None] = mapped_column(JSON)
    velocity_smooth_stream: Mapped[dict | None] = mapped_column(JSON)
    heartrate_stream: Mapped[dict | None] = mapped_column(JSON)
    derived_series: Mapped[dict | None] = mapped_column(JSON)
    interval_analysis: Mapped[dict | None] = mapped_column(JSON)


class PeriodSummary(Base):
    __tablename__ = "period_summaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    sport_type: Mapped[str] = mapped_column(String(50), nullable=False)
    period_type: Mapped[str] = mapped_column(String(20), nullable=False)
    period_start: Mapped[date] = mapped_column(nullable=False)
    activity_count: Mapped[int] = mapped_column(nullable=False, default=0)
    total_distance_meters: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    total_moving_time_seconds: Mapped[int] = mapped_column(nullable=False, default=0)
    average_speed_mps: Mapped[float | None] = mapped_column(Numeric(10, 4))
    average_pace_seconds_per_km: Mapped[float | None] = mapped_column(Numeric(10, 2))
    total_elevation_gain_meters: Mapped[float | None] = mapped_column(Numeric(12, 2))
    total_difficulty_score: Mapped[float | None] = mapped_column(Numeric(12, 4))


class BestEffort(Base):
    __tablename__ = "best_efforts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    sport_type: Mapped[str] = mapped_column(String(50), nullable=False)
    effort_code: Mapped[str] = mapped_column(String(50), nullable=False)
    best_time_seconds: Mapped[int] = mapped_column(nullable=False)
    distance_meters: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    activity_id: Mapped[int | None] = mapped_column(Integer)
    achieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ActivityBestEffort(Base):
    __tablename__ = "activity_best_efforts"

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    effort_code: Mapped[str] = mapped_column(String(50), nullable=False)
    best_time_seconds: Mapped[int] = mapped_column(nullable=False)


class SyncCheckpoint(Base):
    __tablename__ = "sync_checkpoints"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    sync_type: Mapped[str] = mapped_column(String(50), nullable=False)
    checkpoint_value: Mapped[str | None] = mapped_column(String(255))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
