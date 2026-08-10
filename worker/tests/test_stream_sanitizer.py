from app.services.stream_sanitizer import sanitize_stream_payload


def test_stream_sanitizer_removes_artifacts_without_changing_alignment() -> None:
    payload = {
        "time": {"data": [0, 1, 2, 3, 4]},
        "distance": {"data": [0, 3, 50, 53, 56]},
        "latlng": {
            "data": [
                [50.0, 14.0],
                [50.00002, 14.0],
                [51.0, 15.0],
                [50.00006, 14.0],
                [50.00008, 14.0],
            ]
        },
        "altitude": {"data": [200, 201, 250, 203, 204]},
        "velocity_smooth": {"data": [3, 3, -1, 40, 3]},
        "heartrate": {"data": [140, 142, 220, 144, 145]},
    }

    sanitized = sanitize_stream_payload(payload, "Run")

    assert all(len(stream["data"]) == 5 for stream in sanitized.values())
    assert sanitized["distance"]["data"][2] == 15
    assert sanitized["latlng"]["data"][2] is None
    assert sanitized["altitude"]["data"][2] is None
    assert sanitized["velocity_smooth"]["data"][2:4] == [None, None]
    assert sanitized["heartrate"]["data"][2] is None
