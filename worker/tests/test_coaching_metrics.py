from app.services.coaching.metrics import (
    aerobic_decoupling_percent,
    format_duration,
    format_pace,
    heart_rate_zone_shares,
)


def test_format_helpers() -> None:
    assert format_duration(None) is None
    assert format_duration(59) == "0:59"
    assert format_duration(3725) == "1:02:05"
    assert format_pace(312) == "5:12 /km"
    assert format_pace(0) is None


def test_heart_rate_zone_shares_are_time_weighted_and_ignore_pauses() -> None:
    time_values = [0, 10, 20, 30, 40, 500]
    heart_rates = [120, 120, 150, 170, 170, 120]

    shares = heart_rate_zone_shares(
        time_seconds=time_values,
        heartrate_bpm=heart_rates,
        aet_heart_rate_bpm=140,
        ant_heart_rate_bpm=160,
    )

    assert shares == {
        "aet_heart_rate_bpm": 140,
        "ant_heart_rate_bpm": 160,
        "below_aet_percent": 25.0,
        "between_aet_ant_percent": 25.0,
        "above_ant_percent": 50.0,
    }
    assert (
        heart_rate_zone_shares(
            time_seconds=time_values,
            heartrate_bpm=heart_rates,
            aet_heart_rate_bpm=None,
            ant_heart_rate_bpm=160,
        )
        is None
    )


def test_aerobic_decoupling_detects_heart_rate_drift_at_constant_pace() -> None:
    time_values = list(range(0, 3601, 60))
    distance_values = [seconds * 3.0 for seconds in time_values]
    heart_rates = [140 if seconds <= 1800 else 154 for seconds in time_values]

    decoupling = aerobic_decoupling_percent(
        distance_meters=distance_values,
        time_seconds=time_values,
        heartrate_bpm=heart_rates,
    )

    assert decoupling is not None
    assert 8.0 < decoupling < 10.0
    assert (
        aerobic_decoupling_percent(
            distance_meters=distance_values[:10],
            time_seconds=time_values[:10],
            heartrate_bpm=heart_rates[:10],
        )
        is None
    )
