from app.application.analytics.running_analysis import _empty_block, _round_metric, _share, _update_longest_block


def _speed_band(value_kph: float, average_speed_kph: float) -> str:
    if average_speed_kph <= 0:
        return "steady_speed"
    if value_kph < average_speed_kph * 0.85:
        return "below_steady"
    if value_kph <= average_speed_kph * 1.15:
        return "steady_speed"
    return "above_steady"


def _heart_rate_band(value_bpm: float, *, aet: float, ant: float) -> str:
    if value_bpm < aet:
        return "below_aet"
    if value_bpm < ant:
        return "between_aet_ant"
    return "above_ant"


def _block_or_none(block: dict[str, float]) -> dict[str, float] | None:
    return block if block["distance_km"] > 0 else None


def _distribution(items: dict[str, float], total_distance: float, labels: dict[str, str]) -> list[dict[str, float | str]]:
    return [
        {
            "code": code,
            "label": labels[code],
            "distance_km": _round_metric(items.get(code, 0.0)),
            "share_percent": _share(items.get(code, 0.0), total_distance),
        }
        for code in labels
    ]


def _activity_evaluation(
    *,
    heart_rate_distribution: list[dict[str, float | str]] | None,
    climbing_share_percent: float,
    heart_rate_drift_bpm: float | None,
    above_threshold_block_distance: float,
) -> str:
    if heart_rate_distribution:
        below_aet_share = next(item["share_percent"] for item in heart_rate_distribution if item["code"] == "below_aet")
        above_ant_share = next(item["share_percent"] for item in heart_rate_distribution if item["code"] == "above_ant")
        if above_ant_share >= 15 or above_threshold_block_distance >= 1.0:
            if climbing_share_percent >= 30:
                return "This looked like a hilly ride with meaningful high-cardiac-load segments on the climbs."
            return "This looked like a harder ride, with meaningful time above your heart-rate threshold."
        if below_aet_share >= 60:
            return "This looked like an aerobic ride, with most of the work staying below your aerobic heart-rate threshold."
    if climbing_share_percent >= 35:
        return "This looked like a terrain-driven ride, with a large share of the distance spent climbing."
    if heart_rate_drift_bpm is not None and heart_rate_drift_bpm >= 5:
        return "This ride stayed moderate on speed, but heart-rate drift suggests the effort became more demanding over time."
    return "This looked like a mostly steady ride, with load shaped more by terrain and pacing than by repeated hard surges."


def _further_training_suggestion(
    *,
    heart_rate_distribution: list[dict[str, float | str]] | None,
    heart_rate_drift_bpm: float | None,
    above_threshold_block_distance: float,
) -> str:
    if heart_rate_distribution:
        above_ant_share = next(item["share_percent"] for item in heart_rate_distribution if item["code"] == "above_ant")
        if above_ant_share >= 15 or above_threshold_block_distance >= 1.0:
            return "Follow this with an easier spin or recovery day so the harder cardiovascular load has room to absorb."
    if heart_rate_drift_bpm is not None and heart_rate_drift_bpm >= 5:
        return "Use the next ride as a steady aerobic spin and check whether heart rate stays more stable for the same speed."
    return "If this matched the plan, repeat a similar steady ride on another endurance day and keep the effort controlled."


def build_cycling_analysis(
    *,
    distance_km: list[float],
    speed_kph: list[float],
    slope_percent: list[float],
    heart_rate_bpm: list[float],
    average_cadence: float | None,
    heart_rate_drift_bpm: float | None,
    aet_heart_rate_bpm: float | None,
    ant_heart_rate_bpm: float | None,
) -> dict | None:
    if not distance_km or not speed_kph:
        return None

    total_distance = max(distance_km[-1] - distance_km[0], 0.0) if len(distance_km) > 1 else 0.0
    if total_distance <= 0:
        return None

    average_speed = sum(speed_kph) / len(speed_kph)
    speed_distances = {"below_steady": 0.0, "steady_speed": 0.0, "above_steady": 0.0}
    terrain_distances = {"climbing": 0.0, "flat": 0.0, "descending": 0.0}
    heart_rate_distances = {"below_aet": 0.0, "between_aet_ant": 0.0, "above_ant": 0.0}

    steady_aerobic_block = _empty_block()
    above_threshold_block = _empty_block()
    current_steady = None
    current_above = None
    has_hr_thresholds = aet_heart_rate_bpm is not None and ant_heart_rate_bpm is not None and bool(heart_rate_bpm)

    for index in range(1, min(len(distance_km), len(speed_kph), len(slope_percent) if slope_percent else len(speed_kph), len(heart_rate_bpm) if heart_rate_bpm else len(speed_kph))):
        start_distance = float(distance_km[index - 1])
        end_distance = float(distance_km[index])
        segment_distance = max(end_distance - start_distance, 0.0)
        if segment_distance <= 0:
            continue

        speed_band = _speed_band(float(speed_kph[index]), average_speed)
        speed_distances[speed_band] += segment_distance

        slope_value = float(slope_percent[index]) if slope_percent else 0.0
        if slope_value > 1.0:
            terrain_distances["climbing"] += segment_distance
        elif slope_value < -1.0:
            terrain_distances["descending"] += segment_distance
        else:
            terrain_distances["flat"] += segment_distance

        if has_hr_thresholds and index < len(heart_rate_bpm):
            hr_band = _heart_rate_band(
                float(heart_rate_bpm[index]),
                aet=float(aet_heart_rate_bpm),
                ant=float(ant_heart_rate_bpm),
            )
            heart_rate_distances[hr_band] += segment_distance

            if hr_band == "below_aet":
                current_steady = {
                    "start_distance_km": start_distance if current_steady is None else current_steady["start_distance_km"],
                    "end_distance_km": end_distance,
                }
            else:
                current_steady = _update_longest_block(current_steady, steady_aerobic_block, start=0.0, end=0.0)

            if hr_band == "above_ant":
                current_above = {
                    "start_distance_km": start_distance if current_above is None else current_above["start_distance_km"],
                    "end_distance_km": end_distance,
                }
            else:
                current_above = _update_longest_block(current_above, above_threshold_block, start=0.0, end=0.0)

    _update_longest_block(current_steady, steady_aerobic_block, start=0.0, end=0.0)
    _update_longest_block(current_above, above_threshold_block, start=0.0, end=0.0)

    speed_distribution = _distribution(
        speed_distances,
        total_distance,
        {
            "below_steady": "Below Steady",
            "steady_speed": "Steady Speed",
            "above_steady": "Above Steady",
        },
    )
    heart_rate_distribution = (
        _distribution(
            heart_rate_distances,
            total_distance,
            {
                "below_aet": "Below AeT",
                "between_aet_ant": "AeT to AnT",
                "above_ant": "Above AnT",
            },
        )
        if has_hr_thresholds
        else None
    )
    climbing_summary = {
        "climbing_distance_km": _round_metric(terrain_distances["climbing"]),
        "climbing_share_percent": _share(terrain_distances["climbing"], total_distance),
        "flat_distance_km": _round_metric(terrain_distances["flat"]),
        "flat_share_percent": _share(terrain_distances["flat"], total_distance),
        "descending_distance_km": _round_metric(terrain_distances["descending"]),
        "descending_share_percent": _share(terrain_distances["descending"], total_distance),
    }

    return {
        "speed_distribution": speed_distribution,
        "heart_rate_distribution": heart_rate_distribution,
        "climbing_summary": climbing_summary,
        "steady_aerobic_block": _block_or_none(steady_aerobic_block),
        "above_threshold_block": _block_or_none(above_threshold_block),
        "average_cadence": _round_metric(float(average_cadence)) if average_cadence is not None else None,
        "activity_evaluation": _activity_evaluation(
            heart_rate_distribution=heart_rate_distribution,
            climbing_share_percent=climbing_summary["climbing_share_percent"],
            heart_rate_drift_bpm=heart_rate_drift_bpm,
            above_threshold_block_distance=above_threshold_block["distance_km"],
        ),
        "further_training_suggestion": _further_training_suggestion(
            heart_rate_distribution=heart_rate_distribution,
            heart_rate_drift_bpm=heart_rate_drift_bpm,
            above_threshold_block_distance=above_threshold_block["distance_km"],
        ),
    }
