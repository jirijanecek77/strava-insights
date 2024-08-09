from dash_apps.run_together.utils.interval import extract_intervals


def test_extract_intervals_within_range():
    distance_km = [0, 1, 2, 3, 4, 5, 6]
    pace = [3.5, 3.6, 4.1, 4.2, 3.9, 3.8, 3.6]
    bpm = [150, 155, 160, 162, 158, 157, 159]
    lower_bound = 3.5
    upper_bound = 4.0

    expected_intervals = [
        {
            'distance_km': [0, 1],
            'pace': [3.5, 3.6],
            'bpm': [150, 155]
        },
        {
            'distance_km': [4, 5, 6],
            'pace': [3.9, 3.8, 3.6],
            'bpm': [158, 157, 159]
        }
    ]

    intervals = extract_intervals(distance_km, pace, bpm, lower_bound, upper_bound)
    assert intervals == expected_intervals


def test_extract_intervals_above_threshold():
    distance_km = [0, 1, 2, 3, 4, 5, 6]
    pace = [3.5, 3.6, 4.1, 4.2, 3.9, 3.8, 4.0]
    bpm = [150, 155, 160, 162, 158, 157, 159]
    lower_bound = 4.0
    upper_bound = float('inf')  # Use infinity for the upper bound to cover all values above the threshold

    expected_intervals = [
        {
            'distance_km': [2, 3],
            'pace': [4.1, 4.2],
            'bpm': [160, 162]
        },
        {
            'distance_km': [6],
            'pace': [4.0],
            'bpm': [159]
        },
    ]

    intervals = extract_intervals(distance_km, pace, bpm, lower_bound, upper_bound)
    assert intervals == expected_intervals


def test_extract_intervals_no_result():
    distance_km = [0, 1, 2, 3, 4, 5, 6]
    pace = [4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7]
    bpm = [150, 155, 160, 162, 158, 157, 159]
    lower_bound = 5.0
    upper_bound = 6

    expected_intervals = []

    intervals = extract_intervals(distance_km, pace, bpm, lower_bound, upper_bound)
    assert intervals == expected_intervals




