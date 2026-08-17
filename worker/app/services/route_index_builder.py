import logging
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import ActivityRouteMembership, ActivityRouteSignature, RouteGroup
from app.repositories import (
    ActivityRepository,
    ActivityStreamRepository,
    LocalRouteRepository,
)
from app.services.local_route_matcher import (
    ROUTE_MODEL_VERSION,
    LocalRouteMatcher,
    RouteInput,
)

SUPPORTED_ROUTE_SPORTS = {"Run", "Ride", "EBikeRide"}
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RouteIndexStats:
    eligible_activity_count: int
    excluded_activity_count: int
    route_group_count: int
    matched_activity_count: int
    compared_pair_count: int
    matched_pair_count: int


class RouteIndexBuilder:
    def __init__(
        self, session: Session, *, matcher: LocalRouteMatcher | None = None
    ) -> None:
        self.activities = ActivityRepository(session)
        self.activity_streams = ActivityStreamRepository(session)
        self.local_routes = LocalRouteRepository(session)
        self.matcher = matcher or LocalRouteMatcher()

    def rebuild_for_user(self, user_id: int) -> RouteIndexStats:
        activities = [
            activity
            for activity in self.activities.list_for_user(user_id)
            if activity.sport_type in SUPPORTED_ROUTE_SPORTS
        ]
        streams = {
            stream.activity_id: stream
            for stream in self.activity_streams.get_by_activity_ids(
                [activity.id for activity in activities]
            )
        }
        result = self.matcher.group(
            [
                RouteInput(
                    activity_id=activity.id,
                    sport_type=activity.sport_type,
                    distance_meters=float(activity.distance_meters),
                    coordinates=(
                        (streams[activity.id].latlng_stream or {}).get("data", [])
                        if activity.id in streams
                        else []
                    ),
                )
                for activity in activities
            ]
        )
        signature_by_activity_id = {
            signature.activity_id: signature for signature in result.signatures
        }
        signatures = [
            ActivityRouteSignature(
                activity_id=signature.activity_id,
                user_id=user_id,
                sport_type=signature.sport_type,
                algorithm_version=ROUTE_MODEL_VERSION,
                source_point_count=signature.source_point_count,
                valid_point_count=signature.valid_point_count,
                distance_meters=Decimal(str(signature.distance_meters)),
                is_loop=signature.is_loop,
                sampled_points=[list(point) for point in signature.sampled_points],
                spatial_cells=sorted(signature.spatial_cells),
            )
            for signature in result.signatures
        ]
        groups: list[tuple[RouteGroup, list[ActivityRouteMembership]]] = []
        for matched_group in result.groups:
            representative = signature_by_activity_id[
                matched_group.representative_activity_id
            ]
            route_group = RouteGroup(
                user_id=user_id,
                sport_type=representative.sport_type,
                representative_activity_id=representative.activity_id,
                algorithm_version=ROUTE_MODEL_VERSION,
                nominal_distance_meters=Decimal(str(representative.distance_meters)),
            )
            memberships = [
                ActivityRouteMembership(
                    activity_id=member.activity_id,
                    similarity_score=Decimal(str(member.similarity_score)),
                )
                for member in matched_group.members
            ]
            groups.append((route_group, memberships))

        self.local_routes.replace_for_user(
            user_id=user_id,
            signatures=signatures,
            groups=groups,
        )
        matched_groups = [group for group in result.groups if len(group.members) >= 2]
        stats = RouteIndexStats(
            eligible_activity_count=len(result.signatures),
            excluded_activity_count=len(result.excluded_activity_ids),
            route_group_count=len(matched_groups),
            matched_activity_count=sum(len(group.members) for group in matched_groups),
            compared_pair_count=result.compared_pair_count,
            matched_pair_count=result.matched_pair_count,
        )
        logger.info(
            "Rebuilt local route index for user.",
            extra={
                "user.id": user_id,
                "route.eligible_activity_count": stats.eligible_activity_count,
                "route.excluded_activity_count": stats.excluded_activity_count,
                "route.group_count": stats.route_group_count,
                "route.matched_activity_count": stats.matched_activity_count,
                "route.compared_pair_count": stats.compared_pair_count,
                "route.matched_pair_count": stats.matched_pair_count,
            },
        )
        return stats
