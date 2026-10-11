from app.services.coaching.metrics import (
    aerobic_decoupling_percent,
    compute_splits,
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


def test_run_splits_report_pace_heart_rate_and_elevation_per_kilometer() -> None:
    # 2.5 km at a steady 5:00 /km, one sample every 10 s (33.3 m).
    time_values = list(range(0, 751, 10))
    distance_values = [seconds * 1000 / 300 for seconds in time_values]
    heart_rates = [140 if seconds < 300 else 150 for seconds in time_values]
    altitudes = [200 + seconds / 30 for seconds in time_values]

    splits = compute_splits(
        sport_type="Run",
        distance_meters=distance_values,
        time_seconds=time_values,
        heartrate_bpm=heart_rates,
        altitude_meters=altitudes,
    )

    assert [split["split"] for split in splits] == [1, 2, 3]
    assert splits[0]["pace"] == "5:00 /km"
    assert splits[0]["distance_km"] == 1.0
    assert splits[0]["avg_hr_bpm"] == 140
    assert splits[1]["avg_hr_bpm"] == 150
    assert splits[0]["elevation_change_m"] == 10
    # The trailing 0.5 km is kept because it is at least 30% of a split.
    assert splits[2]["distance_km"] == 0.5


def test_ride_splits_use_speed_and_skip_missing_samples() -> None:
    time_values = [0, 300, None, 600]
    distance_values = [0, 2500, 3000, 5000]

    splits = compute_splits(sport_type="Ride", distance_meters=distance_values, time_seconds=time_values)

    assert splits == [{"split": 1, "distance_km": 5.0, "speed_kph": 30.0}]


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
        "aet_to_ant_percent": 25.0,
        "above_ant_percent": 50.0,
    }
    assert heart_rate_zone_shares(
        time_seconds=time_values, heartrate_bpm=heart_rates, aet_heart_rate_bpm=None, ant_heart_rate_bpm=160
    ) is None


def test_aerobic_decoupling_detects_heart_rate_drift_at_constant_pace() -> None:
    time_values = list(range(0, 3601, 60))
    distance_values = [seconds * 3.0 for seconds in time_values]
    heart_rates = [140 if seconds <= 1800 else 154 for seconds in time_values]

    decoupling = aerobic_decoupling_percent(
        distance_meters=distance_values, time_seconds=time_values, heartrate_bpm=heart_rates
    )

    assert decoupling is not None
    assert 8.0 < decoupling < 10.0
    assert aerobic_decoupling_percent(
        distance_meters=distance_values[:10], time_seconds=time_values[:10], heartrate_bpm=heart_rates[:10]
    ) is None
