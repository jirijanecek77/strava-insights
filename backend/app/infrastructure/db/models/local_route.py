from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.infrastructure.db.base import Base


class ActivityRouteSignature(Base):
    __tablename__ = "activity_route_signatures"
    __table_args__ = (
        Index(
            "ix_route_signatures_user_sport_distance",
            "user_id",
            "sport_type",
            "distance_meters",
        ),
        Index(
            "ix_route_signatures_spatial_cells",
            "spatial_cells",
            postgresql_using="gin",
        ),
    )

    activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    sport_type: Mapped[str] = mapped_column(String(50), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(32), nullable=False)
    source_point_count: Mapped[int] = mapped_column(nullable=False)
    valid_point_count: Mapped[int] = mapped_column(nullable=False)
    distance_meters: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    is_loop: Mapped[bool] = mapped_column(Boolean, nullable=False)
    sampled_points: Mapped[list[list[float]]] = mapped_column(JSONB, nullable=False)
    spatial_cells: Mapped[list[str]] = mapped_column(ARRAY(String(15)), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RouteGroup(Base):
    __tablename__ = "route_groups"
    __table_args__ = (Index("ix_route_groups_user_sport", "user_id", "sport_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    sport_type: Mapped[str] = mapped_column(String(50), nullable=False)
    representative_activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"), nullable=False
    )
    algorithm_version: Mapped[str] = mapped_column(String(32), nullable=False)
    nominal_distance_meters: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ActivityRouteMembership(Base):
    __tablename__ = "activity_route_memberships"
    __table_args__ = (Index("ix_activity_route_memberships_group", "route_group_id"),)

    activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"), primary_key=True
    )
    route_group_id: Mapped[int] = mapped_column(
        ForeignKey("route_groups.id", ondelete="CASCADE"), nullable=False
    )
    similarity_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
