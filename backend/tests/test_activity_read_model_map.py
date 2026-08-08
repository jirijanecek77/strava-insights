from app.application.read_models.activities import _activity_map_from_latlng


def test_activity_map_keeps_valid_strava_polyline_points() -> None:
    activity_map = _activity_map_from_latlng(
        [[50.0, 14.0], None, [None, 14.05], [50.1, 14.1], [50.2]]
    )

    assert activity_map is not None
    assert activity_map.polyline == [[50.0, 14.0], [50.1, 14.1]]
    assert activity_map.bounds == {
        "min_lat": 50.0,
        "max_lat": 50.1,
        "min_lng": 14.0,
        "max_lng": 14.1,
    }


def test_activity_map_omits_intervals_scalar_coordinate_stream() -> None:
    assert _activity_map_from_latlng([None, 48.858246, 48.85829, 48.858265]) is None
