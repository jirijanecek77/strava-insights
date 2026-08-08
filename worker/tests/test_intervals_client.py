from app.intervals_client import IntervalsApiClient


def test_intervals_stream_normalizer_zips_latlng_data_and_data2() -> None:
    payload = [
        {
            "type": "latlng",
            "data": [None, 48.858246, 48.85829],
            "data2": [None, 17.020842, 17.020815],
        },
        {
            "type": "velocity_smooth",
            "data": [None, 3.2, 3.4],
        },
    ]

    normalized = IntervalsApiClient._normalize_stream_payload(payload)

    assert normalized["latlng"] == {
        "data": [None, [48.858246, 17.020842], [48.85829, 17.020815]]
    }
    assert normalized["velocity_smooth"]["data"] == [None, 3.2, 3.4]


def test_intervals_stream_normalizer_keeps_legacy_latlng_pairs() -> None:
    payload = {"latlng": [[50.0, 14.0], [50.1, 14.1]]}

    normalized = IntervalsApiClient._normalize_stream_payload(payload)

    assert normalized["latlng"] == {"data": [[50.0, 14.0], [50.1, 14.1]]}
