from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)


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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class GarminCredential(Base):
    __tablename__ = "garmin_credentials"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    email_encrypted: Mapped[str] = mapped_column(String(4096), nullable=False)
    token_json_encrypted: Mapped[str] = mapped_column(String(16384), nullable=False)
    external_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    connection_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="connected"
    )


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_activity_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_provider: Mapped[str] = mapped_column(String(32), nullable=False, default="garmin")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None]
    sport_type: Mapped[str] = mapped_column(String(50), nullable=False)
    start_date_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    start_date_local: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    distance_meters: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    distance_km: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    moving_time_seconds: Mapped[int] = mapped_column(nullable=False)
    moving_time_display: Mapped[str | None] = mapped_column(String(32))
    elapsed_time_seconds: Mapped[int | None]
    total_elevation_gain_meters: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    average_speed_mps: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    average_speed_kph: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    max_speed_mps: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    average_heartrate_bpm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    average_cadence: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    average_pace_seconds_per_km: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    average_pace_display: Mapped[str | None] = mapped_column(String(16))
    summary_metric_display: Mapped[str | None] = mapped_column(String(32))


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


class ActivityRouteSignature(Base):
    __tablename__ = "activity_route_signatures"

    activity_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    sport_type: Mapped[str] = mapped_column(String(50), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(32), nullable=False)
    source_point_count: Mapped[int] = mapped_column(Integer, nullable=False)
    valid_point_count: Mapped[int] = mapped_column(Integer, nullable=False)
    distance_meters: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    is_loop: Mapped[bool] = mapped_column(Boolean, nullable=False)
    sampled_points: Mapped[list[list[float]]] = mapped_column(JSON, nullable=False)
    spatial_cells: Mapped[list[str]] = mapped_column(ARRAY(String(15)), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RouteGroup(Base):
    __tablename__ = "route_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    sport_type: Mapped[str] = mapped_column(String(50), nullable=False)
    representative_activity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(32), nullable=False)
    nominal_distance_meters: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ActivityRouteMembership(Base):
    __tablename__ = "activity_route_memberships"

    activity_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    route_group_id: Mapped[int] = mapped_column(Integer, nullable=False)
    similarity_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PeriodSummary(Base):
    __tablename__ = "period_summaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    sport_type: Mapped[str] = mapped_column(String(50), nullable=False)
    period_type: Mapped[str] = mapped_column(String(20), nullable=False)
    period_start: Mapped[date] = mapped_column(nullable=False)
    activity_count: Mapped[int] = mapped_column(nullable=False, default=0)
    total_distance_meters: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    total_moving_time_seconds: Mapped[int] = mapped_column(nullable=False, default=0)
    average_speed_mps: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    average_pace_seconds_per_km: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    total_elevation_gain_meters: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))


class BestEffort(Base):
    __tablename__ = "best_efforts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    sport_type: Mapped[str] = mapped_column(String(50), nullable=False)
    effort_code: Mapped[str] = mapped_column(String(50), nullable=False)
    best_time_seconds: Mapped[int] = mapped_column(nullable=False)
    distance_meters: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    activity_id: Mapped[int | None] = mapped_column(Integer)
    achieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SyncCheckpoint(Base):
    __tablename__ = "sync_checkpoints"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    sync_type: Mapped[str] = mapped_column(String(50), nullable=False)
    checkpoint_value: Mapped[str | None] = mapped_column(String(255))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
