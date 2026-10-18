from app.services.local_route_matcher import (
    ExistingRouteGroup,
    LocalRouteMatcher,
    RouteInput,
)
from collections.abc import Sequence
from math import cos, pi, sin


def _open_route(*, count: int = 121) -> list[list[float]]:
    return [[50.0, 14.0 + (index * 0.0005)] for index in range(count)]


def _loop_route(*, count: int = 120) -> list[list[float]]:
    points = [
        [
            50.0 + (0.01 * sin((2 * pi * index) / count)),
            14.0 + (0.015 * cos((2 * pi * index) / count)),
        ]
        for index in range(count)
    ]
    return [*points, points[0]]


def _route_input(
    activity_id: int,
        points: Sequence[list[float] | tuple[float, float] | None],
    *,
    distance_meters: float = 4_300.0,
    sport_type: str = "Run",
) -> RouteInput:
    return RouteInput(
        activity_id=activity_id,
        sport_type=sport_type,
        distance_meters=distance_meters,
        coordinates=points,
    )


def _group_member_ids(result) -> set[frozenset[int]]:
    return {frozenset(group.member_activity_ids) for group in result.groups}


def test_matches_same_direction_route_with_small_gps_jitter() -> None:
    original = _open_route()
    jittered = [
        [latitude + (0.00002 if index % 2 else -0.00002), longitude]
        for index, (latitude, longitude) in enumerate(original)
    ]

    result = LocalRouteMatcher().group(
        [_route_input(1, original), _route_input(2, jittered)]
    )

    assert _group_member_ids(result) == {frozenset({1, 2})}
    assert result.groups[0].representative_activity_id == 1


def test_keeps_reversed_open_route_separate() -> None:
    original = _open_route()

    result = LocalRouteMatcher().group(
        [_route_input(1, original), _route_input(2, list(reversed(original)))]
    )

    assert _group_member_ids(result) == {frozenset({1}), frozenset({2})}


def test_matches_same_direction_loop_with_shifted_recording_start() -> None:
    original = _loop_route()
    shifted_core = original[30:-1] + original[:30]
    shifted = [*shifted_core, shifted_core[0]]

    result = LocalRouteMatcher().group(
        [
            _route_input(1, original, distance_meters=7_200.0),
            _route_input(2, shifted, distance_meters=7_200.0),
        ]
    )

    assert _group_member_ids(result) == {frozenset({1, 2})}


def test_keeps_reversed_loop_separate() -> None:
    original = _loop_route()
    reversed_core = list(reversed(original[:-1]))
    reversed_loop = [*reversed_core, reversed_core[0]]

    result = LocalRouteMatcher().group(
        [
            _route_input(1, original, distance_meters=7_200.0),
            _route_input(2, reversed_loop, distance_meters=7_200.0),
        ]
    )

    assert _group_member_ids(result) == {frozenset({1}), frozenset({2})}


def test_rejects_route_with_a_real_detour() -> None:
    original = _open_route()
    detour = [point[:] for point in original]
    for index in range(48, 73):
        progress = (index - 48) / 24
        detour[index][0] += 0.006 * sin(pi * progress)

    result = LocalRouteMatcher().group(
        [_route_input(1, original), _route_input(2, detour)]
    )

    assert _group_member_ids(result) == {frozenset({1}), frozenset({2})}


def test_never_matches_different_sports() -> None:
    route = _open_route()

    result = LocalRouteMatcher().group(
        [
            _route_input(1, route, sport_type="Run"),
            _route_input(2, route, sport_type="Ride"),
        ]
    )

    assert _group_member_ids(result) == {frozenset({1}), frozenset({2})}


def test_excludes_route_with_insufficient_valid_gps() -> None:
    sparse_route: list[list[float] | None] = [None] * 30
    sparse_route[0] = [50.0, 14.0]
    sparse_route[-1] = [50.001, 14.001]

    result = LocalRouteMatcher().group([_route_input(1, sparse_route)])

    assert result.groups == []
    assert result.excluded_activity_ids == [1]


def _detour_route() -> list[list[float]]:
    detour = [point[:] for point in _open_route()]
    for index in range(48, 73):
        progress = (index - 48) / 24
        detour[index][0] += 0.006 * sin(pi * progress)
    return detour


def _signature(activity_id: int, points, **kwargs):
    signature = LocalRouteMatcher().build_signature(
        _route_input(activity_id, points, **kwargs)
    )
    assert signature is not None
    return signature


def test_assign_joins_group_when_every_member_matches() -> None:
    matcher = LocalRouteMatcher()
    original = _open_route()
    jittered = [[latitude + 0.00002, longitude] for latitude, longitude in original]
    candidates = [_signature(1, original), _signature(2, jittered)]

    assignment = matcher.assign(
        _signature(3, original),
        candidates,
        [ExistingRouteGroup(group_id=10, representative_activity_id=1, member_activity_ids=frozenset({1, 2}))],
    )

    assert assignment.group_id == 10
    assert assignment.similarity_score > 0.9
    assert assignment.compared_count == 2


def test_assign_creates_new_group_when_only_some_members_match() -> None:
    matcher = LocalRouteMatcher()
    original = _open_route()
    candidates = [_signature(1, original), _signature(2, _detour_route())]

    assignment = matcher.assign(
        _signature(3, original),
        candidates,
        [ExistingRouteGroup(group_id=10, representative_activity_id=1, member_activity_ids=frozenset({1, 2}))],
    )

    assert assignment.group_id is None
    assert assignment.similarity_score == 1.0


def test_assign_prefers_group_with_highest_average_similarity() -> None:
    matcher = LocalRouteMatcher()
    original = _open_route()
    shifted = [[latitude + 0.0003, longitude] for latitude, longitude in original]
    candidates = [_signature(1, shifted), _signature(2, original)]

    assignment = matcher.assign(
        _signature(3, original),
        candidates,
        [
            ExistingRouteGroup(group_id=10, representative_activity_id=1, member_activity_ids=frozenset({1})),
            ExistingRouteGroup(group_id=11, representative_activity_id=2, member_activity_ids=frozenset({2})),
        ],
    )

    assert assignment.group_id == 11


def test_assign_matches_full_grouping_for_routes_added_one_by_one() -> None:
    matcher = LocalRouteMatcher()
    original = _open_route()
    routes = [
        _route_input(1, original),
        _route_input(2, list(reversed(original))),
        _route_input(3, [[latitude + 0.00002, longitude] for latitude, longitude in original]),
        _route_input(4, _detour_route()),
        _route_input(5, original),
    ]
    full_groups = _group_member_ids(matcher.group(routes))

    signatures = []
    groups: dict[int, set[int]] = {}
    representatives: dict[int, int] = {}
    for route in routes:
        signature = matcher.build_signature(route)
        assert signature is not None
        assignment = matcher.assign(
            signature,
            signatures,
            [
                ExistingRouteGroup(group_id, representatives[group_id], frozenset(members))
                for group_id, members in groups.items()
            ],
        )
        group_id = assignment.group_id or (max(groups, default=0) + 1)
        groups.setdefault(group_id, set()).add(signature.activity_id)
        representatives.setdefault(group_id, signature.activity_id)
        signatures.append(signature)

    assert {frozenset(members) for members in groups.values()} == full_groups
