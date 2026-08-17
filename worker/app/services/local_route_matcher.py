from __future__ import annotations

from dataclasses import dataclass
from math import asin, cos, isfinite, pi, radians, sin, sqrt
from numbers import Real

import h3
from shapely import LineString, Point, frechet_distance, hausdorff_distance

EARTH_RADIUS_METERS = 6_371_000.0
ROUTE_MODEL_VERSION = "1"
MIN_VALID_POINTS = 20
MIN_VALID_POINT_RATIO = 0.80
MIN_ROUTE_DISTANCE_METERS = 500.0
MAX_TOLERATED_GPS_GAP_METERS = 200.0
SAMPLE_SPACING_METERS = 50.0
MAX_SAMPLE_POINTS = 500
MAX_DISTANCE_DIFFERENCE_RATIO = 0.05
MAX_ENDPOINT_DISTANCE_METERS = 150.0
MATCH_DISTANCE_METERS = 75.0
MIN_ROUTE_COVERAGE_RATIO = 0.95
MAX_HAUSDORFF_DISTANCE_METERS = 150.0
MAX_FRECHET_DISTANCE_METERS = 125.0
H3_RESOLUTION = 9

Coordinate = tuple[float, float]
ProjectedPoint = tuple[float, float]


@dataclass(frozen=True, slots=True)
class RouteInput:
    activity_id: int
    sport_type: str
    distance_meters: float
    coordinates: list[list[float] | tuple[float, float] | None]


@dataclass(frozen=True, slots=True)
class RouteSignature:
    activity_id: int
    sport_type: str
    distance_meters: float
    source_point_count: int
    valid_point_count: int
    sampled_points: tuple[Coordinate, ...]
    spatial_cells: frozenset[str]
    is_loop: bool


@dataclass(frozen=True, slots=True)
class RouteGroupMember:
    activity_id: int
    similarity_score: float


@dataclass(frozen=True, slots=True)
class RouteGroup:
    representative_activity_id: int
    members: tuple[RouteGroupMember, ...]

    @property
    def member_activity_ids(self) -> tuple[int, ...]:
        return tuple(member.activity_id for member in self.members)


@dataclass(frozen=True, slots=True)
class RouteMatchResult:
    signatures: list[RouteSignature]
    groups: list[RouteGroup]
    excluded_activity_ids: list[int]
    compared_pair_count: int
    matched_pair_count: int


class LocalRouteMatcher:
    def group(self, routes: list[RouteInput]) -> RouteMatchResult:
        signatures: list[RouteSignature] = []
        excluded_activity_ids: list[int] = []
        for route in sorted(routes, key=lambda item: item.activity_id):
            signature = self._build_signature(route)
            if signature is None:
                excluded_activity_ids.append(route.activity_id)
            else:
                signatures.append(signature)

        pair_scores, compared_pair_count = self._match_pairs(signatures)
        groups = self._build_groups(signatures, pair_scores)
        return RouteMatchResult(
            signatures=signatures,
            groups=groups,
            excluded_activity_ids=excluded_activity_ids,
            compared_pair_count=compared_pair_count,
            matched_pair_count=len(pair_scores),
        )

    def _build_signature(self, route: RouteInput) -> RouteSignature | None:
        source_point_count = len(route.coordinates)
        segments: list[list[Coordinate]] = []
        current_segment: list[Coordinate] = []
        valid_point_count = 0
        for value in route.coordinates:
            point = _coordinate(value)
            if point is None:
                if current_segment:
                    segments.append(current_segment)
                    current_segment = []
                continue
            valid_point_count += 1
            if not current_segment or _haversine_meters(current_segment[-1], point) > 0.5:
                current_segment.append(point)
        if current_segment:
            segments.append(current_segment)

        if (
            source_point_count == 0
            or valid_point_count < MIN_VALID_POINTS
            or valid_point_count / source_point_count < MIN_VALID_POINT_RATIO
        ):
            return None

        merged_points = _merge_short_gaps(segments)
        if merged_points is None or len(merged_points) < MIN_VALID_POINTS:
            return None

        path_distance = _path_distance_meters(merged_points)
        if (
            route.distance_meters < MIN_ROUTE_DISTANCE_METERS
            or path_distance < MIN_ROUTE_DISTANCE_METERS
        ):
            return None

        sampled_points = tuple(_resample_route(merged_points))
        if len(sampled_points) < MIN_VALID_POINTS:
            return None
        loop_threshold = max(100.0, min(500.0, path_distance * 0.02))
        is_loop = _haversine_meters(sampled_points[0], sampled_points[-1]) <= loop_threshold
        spatial_cells = frozenset(
            h3.latlng_to_cell(latitude, longitude, H3_RESOLUTION)
            for latitude, longitude in sampled_points
        )
        return RouteSignature(
            activity_id=route.activity_id,
            sport_type=route.sport_type,
            distance_meters=route.distance_meters,
            source_point_count=source_point_count,
            valid_point_count=valid_point_count,
            sampled_points=sampled_points,
            spatial_cells=spatial_cells,
            is_loop=is_loop,
        )

    def _match_pairs(
        self, signatures: list[RouteSignature]
    ) -> tuple[dict[tuple[int, int], float], int]:
        signature_by_id = {signature.activity_id: signature for signature in signatures}
        cell_index: dict[tuple[str, str], set[int]] = {}
        pair_scores: dict[tuple[int, int], float] = {}
        compared_pairs: set[tuple[int, int]] = set()

        for signature in signatures:
            candidate_ids: set[int] = set()
            for cell in signature.spatial_cells:
                for nearby_cell in h3.grid_disk(cell, 1):
                    candidate_ids.update(
                        cell_index.get((signature.sport_type, nearby_cell), set())
                    )

            for candidate_id in sorted(candidate_ids):
                candidate = signature_by_id[candidate_id]
                pair_key = _pair_key(candidate.activity_id, signature.activity_id)
                if pair_key in compared_pairs or not _distance_is_comparable(
                    candidate.distance_meters, signature.distance_meters
                ):
                    continue
                compared_pairs.add(pair_key)
                score = _similarity_score(candidate, signature)
                if score is not None:
                    pair_scores[pair_key] = score

            for cell in signature.spatial_cells:
                cell_index.setdefault((signature.sport_type, cell), set()).add(
                    signature.activity_id
                )

        return pair_scores, len(compared_pairs)

    def _build_groups(
        self,
        signatures: list[RouteSignature],
        pair_scores: dict[tuple[int, int], float],
    ) -> list[RouteGroup]:
        clusters = [{signature.activity_id} for signature in signatures]
        edges = sorted(
            pair_scores,
            key=lambda pair: (-pair_scores[pair], pair[0], pair[1]),
        )
        for left_id, right_id in edges:
            left_index = next(
                index for index, cluster in enumerate(clusters) if left_id in cluster
            )
            right_index = next(
                index for index, cluster in enumerate(clusters) if right_id in cluster
            )
            if left_index == right_index:
                continue
            left_cluster = clusters[left_index]
            right_cluster = clusters[right_index]
            if not all(
                _pair_key(left_member, right_member) in pair_scores
                for left_member in left_cluster
                for right_member in right_cluster
            ):
                continue
            merged = left_cluster | right_cluster
            for index in sorted((left_index, right_index), reverse=True):
                clusters.pop(index)
            clusters.append(merged)

        groups: list[RouteGroup] = []
        for cluster in sorted(clusters, key=lambda members: min(members)):
            representative_id = _representative_activity_id(cluster, pair_scores)
            members = tuple(
                RouteGroupMember(
                    activity_id=activity_id,
                    similarity_score=(
                        1.0
                        if activity_id == representative_id
                        else pair_scores[_pair_key(activity_id, representative_id)]
                    ),
                )
                for activity_id in sorted(cluster)
            )
            groups.append(
                RouteGroup(
                    representative_activity_id=representative_id,
                    members=members,
                )
            )
        return groups


def _coordinate(
    value: list[float] | tuple[float, float] | None,
) -> Coordinate | None:
    if not isinstance(value, list | tuple) or len(value) < 2:
        return None
    latitude = _finite_number(value[0])
    longitude = _finite_number(value[1])
    if (
        latitude is None
        or longitude is None
        or not -90 <= latitude <= 90
        or not -180 <= longitude <= 180
    ):
        return None
    return latitude, longitude


def _finite_number(value: object) -> float | None:
    if not isinstance(value, Real) or isinstance(value, bool):
        return None
    numeric = float(value)
    return numeric if isfinite(numeric) else None


def _merge_short_gaps(segments: list[list[Coordinate]]) -> list[Coordinate] | None:
    non_empty_segments = [segment for segment in segments if len(segment) >= 2]
    if not non_empty_segments:
        return None
    merged = list(non_empty_segments[0])
    for segment in non_empty_segments[1:]:
        if (
            _haversine_meters(merged[-1], segment[0])
            > MAX_TOLERATED_GPS_GAP_METERS
        ):
            return None
        merged.extend(segment)
    return merged


def _resample_route(points: list[Coordinate]) -> list[Coordinate]:
    sampled = [points[0]]
    distance_to_next_sample = SAMPLE_SPACING_METERS
    previous = points[0]
    for point in points[1:]:
        segment_start = previous
        segment_distance = _haversine_meters(segment_start, point)
        while segment_distance >= distance_to_next_sample and segment_distance > 0:
            fraction = distance_to_next_sample / segment_distance
            sampled_point = _interpolate(segment_start, point, fraction)
            sampled.append(sampled_point)
            segment_start = sampled_point
            segment_distance = _haversine_meters(segment_start, point)
            distance_to_next_sample = SAMPLE_SPACING_METERS
        distance_to_next_sample -= segment_distance
        previous = point

    if _haversine_meters(sampled[-1], points[-1]) > 1.0:
        sampled.append(points[-1])
    if len(sampled) <= MAX_SAMPLE_POINTS:
        return sampled
    return [
        sampled[round(index * (len(sampled) - 1) / (MAX_SAMPLE_POINTS - 1))]
        for index in range(MAX_SAMPLE_POINTS)
    ]


def _interpolate(left: Coordinate, right: Coordinate, fraction: float) -> Coordinate:
    return (
        left[0] + ((right[0] - left[0]) * fraction),
        left[1] + ((right[1] - left[1]) * fraction),
    )


def _path_distance_meters(points: list[Coordinate]) -> float:
    return sum(
        _haversine_meters(left, right) for left, right in zip(points, points[1:])
    )


def _haversine_meters(left: Coordinate, right: Coordinate) -> float:
    left_latitude, left_longitude = radians(left[0]), radians(left[1])
    right_latitude, right_longitude = radians(right[0]), radians(right[1])
    delta_latitude = right_latitude - left_latitude
    delta_longitude = right_longitude - left_longitude
    value = (
        sin(delta_latitude / 2) ** 2
        + cos(left_latitude)
        * cos(right_latitude)
        * sin(delta_longitude / 2) ** 2
    )
    return EARTH_RADIUS_METERS * 2 * asin(sqrt(value))


def _distance_is_comparable(left: float, right: float) -> bool:
    maximum = max(left, right)
    return maximum > 0 and abs(left - right) / maximum <= MAX_DISTANCE_DIFFERENCE_RATIO


def _similarity_score(
    left: RouteSignature, right: RouteSignature
) -> float | None:
    if left.sport_type != right.sport_type or left.is_loop != right.is_loop:
        return None
    if not left.is_loop and (
        _haversine_meters(left.sampled_points[0], right.sampled_points[0])
        > MAX_ENDPOINT_DISTANCE_METERS
        or _haversine_meters(left.sampled_points[-1], right.sampled_points[-1])
        > MAX_ENDPOINT_DISTANCE_METERS
    ):
        return None

    projected_left, projected_right = _project_pair(
        left.sampled_points, right.sampled_points
    )
    left_line = LineString(projected_left)
    right_line = LineString(projected_right)
    left_coverage = _coverage_ratio(projected_left, right_line)
    right_coverage = _coverage_ratio(projected_right, left_line)
    minimum_coverage = min(left_coverage, right_coverage)
    if minimum_coverage < MIN_ROUTE_COVERAGE_RATIO:
        return None

    hausdorff = float(hausdorff_distance(left_line, right_line, densify=0.25))
    if not isfinite(hausdorff) or hausdorff > MAX_HAUSDORFF_DISTANCE_METERS:
        return None
    frechet = _ordered_frechet_distance(
        projected_left,
        projected_right,
        is_loop=left.is_loop,
    )
    if not isfinite(frechet) or frechet > MAX_FRECHET_DISTANCE_METERS:
        return None

    geometry_score = 1.0 - min(
        1.0,
        (
            (hausdorff / MAX_HAUSDORFF_DISTANCE_METERS)
            + (frechet / MAX_FRECHET_DISTANCE_METERS)
        )
        / 2,
    )
    return round((minimum_coverage * 0.7) + (geometry_score * 0.3), 4)


def _project_pair(
    left: tuple[Coordinate, ...], right: tuple[Coordinate, ...]
) -> tuple[list[ProjectedPoint], list[ProjectedPoint]]:
    all_points = [*left, *right]
    origin_latitude = radians(
        sum(point[0] for point in all_points) / len(all_points)
    )
    origin_longitude = radians(
        sum(point[1] for point in all_points) / len(all_points)
    )

    def project(points: tuple[Coordinate, ...]) -> list[ProjectedPoint]:
        return [
            (
                EARTH_RADIUS_METERS
                * (radians(longitude) - origin_longitude)
                * cos(origin_latitude),
                EARTH_RADIUS_METERS * (radians(latitude) - origin_latitude),
            )
            for latitude, longitude in points
        ]

    return project(left), project(right)


def _coverage_ratio(points: list[ProjectedPoint], route: LineString) -> float:
    covered = sum(
        route.distance(Point(point)) <= MATCH_DISTANCE_METERS for point in points
    )
    return covered / len(points)


def _ordered_frechet_distance(
    left: list[ProjectedPoint],
    right: list[ProjectedPoint],
    *,
    is_loop: bool,
) -> float:
    left_line = LineString(left)
    if not is_loop:
        return float(frechet_distance(left_line, LineString(right), densify=0.25))

    left_core = _without_duplicate_closing_point(left)
    right_core = _without_duplicate_closing_point(right)
    closest_indices = sorted(
        range(len(right_core)),
        key=lambda index: _squared_distance(left_core[0], right_core[index]),
    )[:4]
    distances = []
    for index in closest_indices:
        rotated = [*right_core[index:], *right_core[:index]]
        distances.append(
            float(
                frechet_distance(
                    LineString([*left_core, left_core[0]]),
                    LineString([*rotated, rotated[0]]),
                    densify=0.25,
                )
            )
        )
    return min(distances)


def _without_duplicate_closing_point(
    points: list[ProjectedPoint],
) -> list[ProjectedPoint]:
    if len(points) > 2 and _squared_distance(points[0], points[-1]) <= 1.0:
        return points[:-1]
    return points


def _squared_distance(left: ProjectedPoint, right: ProjectedPoint) -> float:
    return ((left[0] - right[0]) ** 2) + ((left[1] - right[1]) ** 2)


def _pair_key(left_id: int, right_id: int) -> tuple[int, int]:
    return min(left_id, right_id), max(left_id, right_id)


def _representative_activity_id(
    members: set[int], pair_scores: dict[tuple[int, int], float]
) -> int:
    if len(members) == 1:
        return next(iter(members))
    average_scores = {
        member: sum(
            1.0 if member == other else pair_scores[_pair_key(member, other)]
            for other in members
        )
        / len(members)
        for member in members
    }
    return min(members, key=lambda member: (-average_scores[member], member))
