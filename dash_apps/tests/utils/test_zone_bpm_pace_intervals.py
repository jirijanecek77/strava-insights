from dash_apps.run_together.utils.interval import get_zone_pace_bpm
from dash_apps.run_together.utils.interval import get_bpm_pace_zone_intervals

def test_get_zone_pace_bpm_within_zone():
    pace_bpm_mapping = {
        "5km": {
            "pace": 4.0,
            "bpm": 150,
            "range_zone_pace": (3.9, 4.1),
            "range_zone_bpm": (145, 155),
            "color": "red"
        },
        "10km": {
            "pace": 5.0,
            "bpm": 140,
            "range_zone_pace": (4.9, 5.1),
            "range_zone_bpm": (135, 145),
            "color": "orange"
        }
    }

    result = get_zone_pace_bpm(pace_bpm_mapping, 4.0, 150)
    expected = {"zone_pace": "5km", "zone_heart_rate": "5km"}

    assert result == expected, f"Expected: {expected}, but got: {result}"


def test_get_zone_pace_bpm_different_zones():
    pace_bpm_mapping = {
        "5km": {
            "pace": 4.0,
            "bpm": 150,
            "range_zone_pace": (3.9, 4.1),
            "range_zone_bpm": (145, 155),
            "color": "red"
        },
        "10km": {
            "pace": 5.0,
            "bpm": 140,
            "range_zone_pace": (4.9, 5.1),
            "range_zone_bpm": (135, 145),
            "color": "orange"
        }
    }

    result = get_zone_pace_bpm(pace_bpm_mapping, 4.0, 140)
    expected = {"zone_pace": "5km", "zone_heart_rate": "10km"}

    assert result == expected, f"Expected: {expected}, but got: {result}"


def test_get_zone_pace_bpm_outside_all_zones():
    pace_bpm_mapping = {
        "5km": {
            "pace": 4.0,
            "bpm": 150,
            "range_zone_pace": (3.9, 4.1),
            "range_zone_bpm": (145, 155),
            "color": "red"
        },
        "10km": {
            "pace": 5.0,
            "bpm": 140,
            "range_zone_pace": (4.9, 5.1),
            "range_zone_bpm": (135, 145),
            "color": "orange"
        }
    }

    result = get_zone_pace_bpm(pace_bpm_mapping=pace_bpm_mapping, pace=6.0, heart_rate=160)
    expected = {"zone_pace": "Unknown", "zone_heart_rate": "Unknown"}

    assert result == expected, f"Expected: {expected}, but got: {result}"


def test_get_zone_pace_bpm_on_boundary():
    pace_bpm_mapping = {
        "5km": {
            "pace": 4.0,
            "bpm": 150,
            "range_zone_pace": (3.9, 4.1),
            "range_zone_bpm": (145, 155),
            "color": "red"
        },
        "10km": {
            "pace": 5.0,
            "bpm": 140,
            "range_zone_pace": (4.9, 5.1),
            "range_zone_bpm": (135, 145),
            "color": "orange"
        }
    }

    result = get_zone_pace_bpm(pace_bpm_mapping, 3.9, 155)
    expected = {"zone_pace": "5km", "zone_heart_rate": "Unknown"}

    assert result == expected, f"Expected: {expected}, but got: {result}"


def test_get_bpm_pace_zone_intervals_single_interval():
    pace_bpm_mapping = {
        "Zone1": {
            "range_zone_pace": (3.0, 4.0),
            "range_zone_bpm": (140, 160),
        },
    }
    distance_km = [0, 1, 2, 3]
    paces = [3.5, 3.6, 3.7, 3.8]
    bpm = [145, 150, 155, 150]

    expected_intervals = [
        {
            'distance_km': [0, 1, 2, 3],
            'pace': [3.5, 3.6, 3.7, 3.8],
            'heart_rate': [145, 150, 155, 150],
            'zones': {"zone_pace": "Zone1", "zone_heart_rate": "Zone1"}
        }
    ]

    intervals = get_bpm_pace_zone_intervals(distance_km, paces, bpm, pace_bpm_mapping)
    assert intervals == expected_intervals, f"Expected: {expected_intervals}, but got: {intervals}"

def test_get_bpm_pace_zone_intervals_multiple_intervals():
    pace_bpm_mapping = {
        "Zone1": {
            "range_zone_pace": (3.0, 4.0),
            "range_zone_bpm": (140, 160),
        },
        "Zone2": {
            "range_zone_pace": (4.0, 5.0),
            "range_zone_bpm": (160, 180),
        }
    }
    distance_km = [0, 1, 2, 3, 4, 5]
    paces = [3.5, 3.6, 4.1, 4.2, 3.8, 3.0]
    bpm = [145, 150, 165, 170, 155, 140]

    expected_intervals = [
        {
            'distance_km': [0, 1],
            'pace': [3.5, 3.6],
            'heart_rate': [145, 150],
            'zones': {"zone_pace": "Zone1", "zone_heart_rate": "Zone1"}
        },
        {
            'distance_km': [2, 3],
            'pace': [4.1, 4.2],
            'heart_rate': [165, 170],
            'zones': {"zone_pace": "Zone2", "zone_heart_rate": "Zone2"}
        },
        {
            'distance_km': [4, 5],
            'pace': [3.8, 3.0],
            'heart_rate': [155, 140],
            'zones': {"zone_pace": "Zone1", "zone_heart_rate": "Zone1"}
        }
    ]

    intervals = get_bpm_pace_zone_intervals(distance_km, paces, bpm, pace_bpm_mapping)
    assert intervals == expected_intervals, f"Expected: {expected_intervals}, but got: {intervals}"

def test_get_bpm_pace_zone_intervals_no_intervals():
    pace_bpm_mapping = {
        "Zone1": {
            "range_zone_pace": (5.0, 6.0),
            "range_zone_bpm": (160, 180),
        },
    }
    distance_km = [0, 1, 2]
    paces = [4.0, 4.5, 4.9]
    heart_rates = [150, 155, 159]

    expected_intervals = [
        {
            'distance_km': [0, 1, 2],
            'pace': [4.0, 4.5, 4.9],
            'heart_rate': [150, 155, 159],
            'zones': {"zone_pace": "Unknown", "zone_heart_rate": "Unknown"}
        }
    ]

    intervals = get_bpm_pace_zone_intervals(
        distance_km=distance_km,
        paces=paces,
        heart_rates=heart_rates,
        pace_bpm_mapping=pace_bpm_mapping
    )

    assert intervals == expected_intervals, f"Expected: {expected_intervals}, but got: {intervals}"


def test_get_bpm_pace_zone_intervals_boundary_values():
    pace_bpm_mapping = {
        "Zone1": {
            "range_zone_pace": (3.0, 4.0),
            "range_zone_bpm": (140.0, 160.0),
        },
        "Zone2": {
            "range_zone_pace": (4.0, 5.0),
            "range_zone_bpm": (160.0, 180.0),
        }
    }
    distance_km = [0, 1, 2, 3, 4]
    paces = [3.0, 3.9, 4.0, 4.1, 5.0]
    bpm = [140, 155, 160, 165, 170]

    expected_intervals = [
        {
            'distance_km': [0, 1],
            'pace': [3.0, 3.9],
            'heart_rate': [140, 155],
            'zones': {"zone_pace": "Zone1", "zone_heart_rate": "Zone1"}
        },
        {
            'distance_km': [2, 3],
            'pace': [4.0, 4.1],
            'heart_rate': [160, 165],
            'zones': {"zone_pace": "Zone2", "zone_heart_rate": "Zone2"}
        },
        {
            'distance_km': [4],
            'pace': [5.0],
            'heart_rate': [170],
            'zones': {"zone_pace": "Unknown", "zone_heart_rate": "Zone2"}
        }
    ]

    intervals = get_bpm_pace_zone_intervals(
        distance_km=distance_km, paces=paces, heart_rates=bpm, pace_bpm_mapping=pace_bpm_mapping
    )
    assert intervals == expected_intervals, f"Expected: {expected_intervals}, but got: {intervals}"


def test_get_bpm_pace_zone_intervals_three_zones():
    pace_bpm_mapping = {
        "Zone1": {
            "range_zone_pace": (3.0, 4.0),
            "range_zone_bpm": (140.0, 160.0),
        },
        "Zone2": {
            "range_zone_pace": (4.0, 5.0),
            "range_zone_bpm": (160.0, 180.0),
        },
        "Zone3": {
            "range_zone_pace": (5.0, 6.0),
            "range_zone_bpm": (180.0, 205.0),
        }
    }

    distance_km = [0, 1, 2, 3, 4, 5]
    paces = [3.0, 3.9, 4.0, 4.1, 5.0, 5.5]
    bpm = [140, 155, 160, 165, 180, 185]

    expected_intervals = [
        {
            'distance_km': [0, 1],
            'pace': [3.0, 3.9],
            'heart_rate': [140, 155],
            'zones': {"zone_pace": "Zone1", "zone_heart_rate": "Zone1"}
        },
        {
            'distance_km': [2, 3],
            'pace': [4.0, 4.1],
            'heart_rate': [160, 165],
            'zones': {"zone_pace": "Zone2", "zone_heart_rate": "Zone2"}
        },
        {
            'distance_km': [4, 5],
            'pace': [5.0, 5.5],
            'heart_rate': [180, 185],
            'zones': {"zone_pace": "Zone3", "zone_heart_rate": "Zone3"}
        }
    ]

    intervals = get_bpm_pace_zone_intervals(
        distance_km=distance_km, paces=paces, heart_rates=bpm, pace_bpm_mapping=pace_bpm_mapping
    )
    assert intervals == expected_intervals, f"Expected: {expected_intervals}, but got: {intervals}"
