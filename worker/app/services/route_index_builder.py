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
    MAX_DISTANCE_DIFFERENCE_RATIO,
    ROUTE_MODEL_VERSION,
    ExistingRouteGroup,
    LocalRouteMatcher,
    RouteInput,
    RouteSignature,
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


@dataclass(frozen=True, slots=True)
class RouteUpdateStats:
    processed_activity_count: int
    excluded_activity_count: int
    joined_group_count: int
    created_group_count: int
    compared_pair_count: int


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
            _signature_row(user_id, signature) for signature in result.signatures
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

    def update_for_activities(self, user_id: int, activities: list) -> RouteUpdateStats:
        """Adds new activities to existing route groups without regrouping the history."""
        pending = sorted(
            (
                activity
                for activity in activities
                if activity.sport_type in SUPPORTED_ROUTE_SPORTS
            ),
            key=lambda activity: activity.id,
        )
        already_indexed = self.local_routes.list_signature_activity_ids(
            [activity.id for activity in pending]
        )
        pending = [activity for activity in pending if activity.id not in already_indexed]
        streams = {
            stream.activity_id: stream
            for stream in self.activity_streams.get_by_activity_ids(
                [activity.id for activity in pending]
            )
        }
        excluded_count = joined_count = created_count = compared_count = 0
        for activity in pending:
            stream = streams.get(activity.id)
            signature = self.matcher.build_signature(
                RouteInput(
                    activity_id=activity.id,
                    sport_type=activity.sport_type,
                    distance_meters=float(activity.distance_meters),
                    coordinates=(
                        (stream.latlng_stream or {}).get("data", [])
                        if stream is not None
                        else []
                    ),
                )
            )
            if signature is None:
                excluded_count += 1
                continue
            candidates = [
                _signature_from_row(row)
                for row in self.local_routes.list_candidate_signatures(
                    user_id=user_id,
                    sport_type=signature.sport_type,
                    min_distance_meters=signature.distance_meters
                    * (1 - MAX_DISTANCE_DIFFERENCE_RATIO),
                    max_distance_meters=signature.distance_meters
                    / (1 - MAX_DISTANCE_DIFFERENCE_RATIO),
                    spatial_cells=sorted(self.matcher.candidate_cells(signature)),
                )
            ]
            existing_groups = [
                ExistingRouteGroup(
                    group_id=route_group.id,
                    representative_activity_id=route_group.representative_activity_id,
                    member_activity_ids=frozenset(member_ids),
                )
                for route_group, member_ids in self.local_routes.list_groups_with_members(
                    [candidate.activity_id for candidate in candidates]
                )
            ]
            assignment = self.matcher.assign(signature, candidates, existing_groups)
            compared_count += assignment.compared_count
            self.local_routes.add_signature(_signature_row(user_id, signature))
            route_group_id = assignment.group_id
            if route_group_id is None:
                route_group_id = self.local_routes.add_group(
                    RouteGroup(
                        user_id=user_id,
                        sport_type=signature.sport_type,
                        representative_activity_id=signature.activity_id,
                        algorithm_version=ROUTE_MODEL_VERSION,
                        nominal_distance_meters=Decimal(str(signature.distance_meters)),
                    )
                ).id
                created_count += 1
            else:
                joined_count += 1
            self.local_routes.add_membership(
                ActivityRouteMembership(
                    activity_id=signature.activity_id,
                    route_group_id=route_group_id,
                    similarity_score=Decimal(str(assignment.similarity_score)),
                )
            )

        stats = RouteUpdateStats(
            processed_activity_count=len(pending),
            excluded_activity_count=excluded_count,
            joined_group_count=joined_count,
            created_group_count=created_count,
            compared_pair_count=compared_count,
        )
        logger.info(
            "Updated local route index for new activities.",
            extra={
                "user.id": user_id,
                "route.processed_activity_count": stats.processed_activity_count,
                "route.excluded_activity_count": stats.excluded_activity_count,
                "route.joined_group_count": stats.joined_group_count,
                "route.created_group_count": stats.created_group_count,
                "route.compared_pair_count": stats.compared_pair_count,
            },
        )
        return stats


def _signature_row(user_id: int, signature: RouteSignature) -> ActivityRouteSignature:
    return ActivityRouteSignature(
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


def _signature_from_row(row: ActivityRouteSignature) -> RouteSignature:
    return RouteSignature(
        activity_id=row.activity_id,
        sport_type=row.sport_type,
        distance_meters=float(row.distance_meters),
        source_point_count=row.source_point_count,
        valid_point_count=row.valid_point_count,
        sampled_points=tuple(
            (float(latitude), float(longitude)) for latitude, longitude in row.sampled_points
        ),
        spatial_cells=frozenset(row.spatial_cells),
        is_loop=row.is_loop,
    )
