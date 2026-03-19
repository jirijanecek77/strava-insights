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


def _activity_evaluation(
    *,
    dominant_pace_label: str,
    matching_share: float,
    heart_rate_higher_share: float,
    above_threshold_distance: float,
    steady_threshold_distance: float,
) -> str:
    if matching_share >= 75:
        if above_threshold_distance > 1.0:
            return f"This looked like a controlled hard session, with pace and heart rate aligned and meaningful time spent above AnT."
        if steady_threshold_distance > 1.0:
            return f"This looked like a steady threshold session, with pace and heart rate staying well aligned around AeT to AnT."
        return f"This looked controlled overall, with pace and heart rate aligning well and most work centered on {dominant_pace_label}."
    if heart_rate_higher_share >= 25:
        return "This looked more physiologically demanding than pace alone suggests, which can happen with fatigue, heat, hills, or incomplete recovery."
    return "This session looked mixed rather than fully settled, with pace and heart rate drifting between bands."


def _further_training_suggestion(
    *,
    matching_share: float,
    heart_rate_higher_share: float,
    above_threshold_distance: float,
    steady_threshold_distance: float,
) -> str:
    if heart_rate_higher_share >= 25:
        return "Use the next run as an easy aerobic session and watch whether heart rate settles more easily at the same pace."
    if above_threshold_distance > 1.0:
        return "Follow this with recovery or easy aerobic work so the high-intensity load has room to absorb."
    if steady_threshold_distance > 1.0 and matching_share >= 70:
        return "If this session matched the plan, you can repeat similar threshold work on a future quality day and build it gradually."
    return "Keep the next session aligned with your training goal, and use the pace-vs-heart-rate match to check whether the effort stays controlled."


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
    dominant_pace = max(pace_distribution, key=lambda item: float(item["distance_km"]))
    activity_evaluation = _activity_evaluation(
        dominant_pace_label=str(dominant_pace["label"]).lower(),
        matching_share=agreement["matching_share_percent"],
        heart_rate_higher_share=agreement["heart_rate_higher_share_percent"],
        above_threshold_distance=above_threshold_block["distance_km"],
        steady_threshold_distance=steady_threshold_block["distance_km"],
    )
    further_training_suggestion = _further_training_suggestion(
        matching_share=agreement["matching_share_percent"],
        heart_rate_higher_share=agreement["heart_rate_higher_share_percent"],
        above_threshold_distance=above_threshold_block["distance_km"],
        steady_threshold_distance=steady_threshold_block["distance_km"],
    )

    return {
        "pace_distribution": pace_distribution,
        "heart_rate_distribution": heart_rate_distribution,
        "agreement": agreement,
        "steady_threshold_block": steady_threshold_block,
        "above_threshold_block": above_threshold_block,
        "interpretation": _interpret_analysis(pace_distribution, heart_rate_distribution, agreement),
        "activity_evaluation": activity_evaluation,
        "further_training_suggestion": further_training_suggestion,
    }
