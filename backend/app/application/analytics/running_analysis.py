from collections.abc import Iterable


BAND_ORDER = {
    "below_aet": 0,
    "between_aet_ant": 1,
    "above_ant": 2,
}

BAND_LABELS = {
    "below_aet": "Below AeT",
    "between_aet_ant": "AeT to AnT",
    "above_ant": "Above AnT",
}


def _resolve_band(value: float, *, aet: float, ant: float, higher_is_harder: bool) -> str:
    if higher_is_harder:
        if value < aet:
            return "below_aet"
        if value < ant:
            return "between_aet_ant"
        return "above_ant"

    if value > aet:
        return "below_aet"
    if value > ant:
        return "between_aet_ant"
    return "above_ant"


def _empty_block() -> dict[str, float]:
    return {
        "start_distance_km": 0.0,
        "end_distance_km": 0.0,
        "distance_km": 0.0,
    }


def _round_metric(value: float) -> float:
    return round(value, 2)


def _share(distance: float, total_distance: float) -> float:
    if total_distance <= 0:
        return 0.0
    return _round_metric((distance / total_distance) * 100)


def _build_distribution(distances: dict[str, float], total_distance: float) -> list[dict[str, float | str]]:
    return [
        {
            "code": code,
            "label": BAND_LABELS[code],
            "distance_km": _round_metric(distances.get(code, 0.0)),
            "share_percent": _share(distances.get(code, 0.0), total_distance),
        }
        for code in ("below_aet", "between_aet_ant", "above_ant")
    ]


def _update_longest_block(current: dict[str, float] | None, longest: dict[str, float], *, start: float, end: float) -> dict[str, float] | None:
    if current is None:
        return None
    current_distance = current["end_distance_km"] - current["start_distance_km"]
    if current_distance > longest["distance_km"]:
        longest["start_distance_km"] = _round_metric(current["start_distance_km"])
        longest["end_distance_km"] = _round_metric(current["end_distance_km"])
        longest["distance_km"] = _round_metric(current_distance)
    return None


def _interpret_analysis(
    pace_distribution: Iterable[dict[str, float | str]],
    heart_rate_distribution: Iterable[dict[str, float | str]],
    agreement: dict[str, float],
) -> str:
    dominant_pace = max(pace_distribution, key=lambda item: float(item["distance_km"]))
    dominant_heart_rate = max(heart_rate_distribution, key=lambda item: float(item["distance_km"]))
    pace_label = str(dominant_pace["label"]).lower()
    heart_rate_label = str(dominant_heart_rate["label"]).lower()
    matching_share = agreement["matching_share_percent"]
    if matching_share >= 75:
        return f"Pace and heart rate aligned well, with most work sitting at {pace_label}."
    if agreement["heart_rate_higher_share_percent"] > agreement["pace_higher_share_percent"]:
        return f"Heart rate ran hotter than pace, with the effort trending toward {heart_rate_label}."
    if agreement["pace_higher_share_percent"] > 0:
        return f"Pace ran ahead of heart rate, with most work landing at {pace_label}."
    return f"Most work landed at {pace_label}, while heart rate sat mostly at {heart_rate_label}."


def _distribution_share(distribution: Iterable[dict[str, float | str]], code: str) -> float:
    for item in distribution:
        if item["code"] == code:
            return float(item["share_percent"])
    return 0.0


def _is_interval_like(
    *,
    pace_distribution: Iterable[dict[str, float | str]],
    pace_band_transitions: int,
    total_distance: float,
) -> bool:
    if total_distance < 2.0:
        return False
    below_aet_share = _distribution_share(pace_distribution, "below_aet")
    above_ant_share = _distribution_share(pace_distribution, "above_ant")
    mixed_low_high_intensity = below_aet_share >= 15 and above_ant_share >= 15
    frequent_pace_changes = pace_band_transitions >= max(4, int(total_distance // 2))
    return mixed_low_high_intensity and frequent_pace_changes


def build_running_analysis(
    *,
    distance_km: list[float],
    pace_minutes_per_km: list[float],
    heart_rate_bpm: list[float],
    aet_pace_min_per_km: float,
    ant_pace_min_per_km: float,
    aet_heart_rate_bpm: float,
    ant_heart_rate_bpm: float,
) -> dict | None:
    series_length = min(len(distance_km), len(pace_minutes_per_km), len(heart_rate_bpm))
    if series_length < 2:
        return None

    pace_distances = {code: 0.0 for code in BAND_ORDER}
    heart_rate_distances = {code: 0.0 for code in BAND_ORDER}
    matching_distance = 0.0
    pace_higher_distance = 0.0
    heart_rate_higher_distance = 0.0
    total_distance = 0.0
    steady_threshold_block = _empty_block()
    above_threshold_block = _empty_block()
    current_steady: dict[str, float] | None = None
    current_above: dict[str, float] | None = None
    previous_pace_band: str | None = None
    pace_band_transitions = 0

    for index in range(1, series_length):
        start_distance = float(distance_km[index - 1])
        end_distance = float(distance_km[index])
        segment_distance = max(0.0, end_distance - start_distance)
        if segment_distance <= 0:
            continue

        pace_band = _resolve_band(
            float(pace_minutes_per_km[index]),
            aet=aet_pace_min_per_km,
            ant=ant_pace_min_per_km,
            higher_is_harder=False,
        )
        heart_rate_band = _resolve_band(
            float(heart_rate_bpm[index]),
            aet=aet_heart_rate_bpm,
            ant=ant_heart_rate_bpm,
            higher_is_harder=True,
        )

        if previous_pace_band is not None and pace_band != previous_pace_band:
            pace_band_transitions += 1
        previous_pace_band = pace_band

        pace_distances[pace_band] += segment_distance
        heart_rate_distances[heart_rate_band] += segment_distance
        total_distance += segment_distance

        pace_level = BAND_ORDER[pace_band]
        heart_rate_level = BAND_ORDER[heart_rate_band]
        if pace_level == heart_rate_level:
            matching_distance += segment_distance
        elif pace_level > heart_rate_level:
            pace_higher_distance += segment_distance
        else:
            heart_rate_higher_distance += segment_distance

        if pace_band == "between_aet_ant" and heart_rate_band == "between_aet_ant":
            if current_steady is None:
                current_steady = {"start_distance_km": start_distance, "end_distance_km": end_distance}
            else:
                current_steady["end_distance_km"] = end_distance
        else:
            current_steady = _update_longest_block(current_steady, steady_threshold_block, start=start_distance, end=end_distance)

        if pace_band == "above_ant" or heart_rate_band == "above_ant":
            if current_above is None:
                current_above = {"start_distance_km": start_distance, "end_distance_km": end_distance}
            else:
                current_above["end_distance_km"] = end_distance
        else:
            current_above = _update_longest_block(current_above, above_threshold_block, start=start_distance, end=end_distance)

    _update_longest_block(current_steady, steady_threshold_block, start=0.0, end=0.0)
    _update_longest_block(current_above, above_threshold_block, start=0.0, end=0.0)

    if total_distance <= 0:
        return None

    pace_distribution = _build_distribution(pace_distances, total_distance)
    heart_rate_distribution = _build_distribution(heart_rate_distances, total_distance)
    agreement = {
        "matching_distance_km": _round_metric(matching_distance),
        "matching_share_percent": _share(matching_distance, total_distance),
        "pace_higher_distance_km": _round_metric(pace_higher_distance),
        "pace_higher_share_percent": _share(pace_higher_distance, total_distance),
        "heart_rate_higher_distance_km": _round_metric(heart_rate_higher_distance),
        "heart_rate_higher_share_percent": _share(heart_rate_higher_distance, total_distance),
    }
    return {
        "pace_distribution": pace_distribution,
        "heart_rate_distribution": heart_rate_distribution,
        "agreement": agreement,
        "interpretation": _interpret_analysis(pace_distribution, heart_rate_distribution, agreement),
    }
