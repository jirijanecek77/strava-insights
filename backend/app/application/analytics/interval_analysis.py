from statistics import mean

from app.application.analytics.running_zones import RunningZone, resolve_running_zone


ZONE_THRESHOLDS = {
    "100m": {"threshold": 0.5, "priority": 1},
    "5km": {"threshold": 0.5, "priority": 1},
    "10km": {"threshold": 1.0, "priority": 1},
    "Half-Marathon": {"threshold": 2.1, "priority": 1},
    "Marathon": {"threshold": 4.2, "priority": 1},
    "Active Jogging": {"threshold": 0.0, "priority": 0},
    "Slow Jogging": {"threshold": 0.0, "priority": 0},
    "Walk": {"threshold": 0.0, "priority": 0},
}


def group_running_intervals(
    *,
    distance_km: list[float],
    paces: list[float],
    heart_rates: list[float],
    zones: list[RunningZone],
) -> list[dict]:
    if not distance_km or not paces or not heart_rates:
        return []

    intervals = [
        {
            "distance_km": [distance_km[0]],
            "pace": [paces[0]],
            "heart_rate": [heart_rates[0]],
            "zones": resolve_running_zone(zones, pace=paces[0], heart_rate=heart_rates[0]),
        }
    ]

    for index in range(1, len(paces)):
        point_zones = resolve_running_zone(zones, pace=paces[index], heart_rate=heart_rates[index])
        if intervals[-1]["zones"] == point_zones:
            intervals[-1]["distance_km"].append(distance_km[index])
            intervals[-1]["pace"].append(paces[index])
            intervals[-1]["heart_rate"].append(heart_rates[index])
            continue
        intervals.append(
            {
                "distance_km": [distance_km[index]],
                "pace": [paces[index]],
                "heart_rate": [heart_rates[index]],
                "zones": point_zones,
            }
        )
    return intervals


def _interval_kpis(intervals: list[dict]) -> tuple[float, float, float]:
    total_distance = 0.0
    paces: list[float] = []
    heart_rates: list[float] = []
    for interval in intervals:
        total_distance += max(interval["distance_km"]) - min(interval["distance_km"])
        paces.extend(interval["pace"])
        heart_rates.extend(interval["heart_rate"])
    return (mean(paces) if paces else 0.0, mean(heart_rates) if heart_rates else 0.0, total_distance)


def summarize_running_intervals(intervals: list[dict]) -> dict:
    summary: dict[str, dict] = {}
    for interval in intervals:
        pace_zone = interval["zones"]["zone_pace"]
        heart_rate_zone = interval["zones"]["zone_heart_rate"]
        if pace_zone not in summary:
            summary[pace_zone] = {"intervals": []}
        summary[pace_zone]["intervals"].append(interval)
        if heart_rate_zone not in summary[pace_zone]:
            summary[pace_zone][heart_rate_zone] = {"intervals": []}
        summary[pace_zone][heart_rate_zone]["intervals"].append(interval)

    for pace_zone, pace_zone_summary in summary.items():
        average_pace, average_heart_rate, total_distance = _interval_kpis(pace_zone_summary["intervals"])
        pace_zone_summary.pop("intervals", None)
        pace_zone_summary["average_pace"] = average_pace
        pace_zone_summary["average_heart_rate"] = average_heart_rate
        pace_zone_summary["total_distance"] = total_distance
        for heart_rate_zone, zone_summary in list(pace_zone_summary.items()):
            if heart_rate_zone in {"average_pace", "average_heart_rate", "total_distance"}:
                continue
            interval_group = zone_summary.get("intervals", [])
            zone_average_pace, zone_average_heart_rate, zone_total_distance = _interval_kpis(interval_group)
            zone_summary.pop("intervals", None)
            zone_summary["average_pace"] = zone_average_pace
            zone_summary["average_heart_rate"] = zone_average_heart_rate
            zone_summary["total_distance"] = zone_total_distance
    return summary


def build_running_compliance(summary: dict, activity_distance_km: float) -> dict | None:
    zones_to_display: list[dict[str, float | str]] = []
    selected_count = 0
    for pace_zone, threshold in ZONE_THRESHOLDS.items():
        if pace_zone not in summary:
            continue
        if threshold["priority"] == 0 and zones_to_display:
            break
        if summary[pace_zone]["total_distance"] > threshold["threshold"]:
            zones_to_display.append({"distance": summary[pace_zone]["total_distance"], "pace_zone": pace_zone})
            selected_count += 1
            if selected_count == 2:
                break

    if not zones_to_display:
        return None

    dominant_zones = sorted(zones_to_display, key=lambda zone: zone["distance"], reverse=True)
    dominant_zone = dominant_zones[0]
    distance_heart_rate_in_range = 0.0
    for heart_rate_zone in ZONE_THRESHOLDS.keys():
        pace_zone_summary = summary[dominant_zone["pace_zone"]]
        if heart_rate_zone in pace_zone_summary:
            distance_heart_rate_in_range += pace_zone_summary[heart_rate_zone]["total_distance"]
        if heart_rate_zone == dominant_zone["pace_zone"]:
            break

    compliance_score = 0.0
    if dominant_zone["distance"] > 0:
        compliance_score = (distance_heart_rate_in_range / dominant_zone["distance"]) * 100

    analysis_text = f"{round(activity_distance_km, 2)} km:"
    for zone in dominant_zones:
        analysis_text += f" | {round(zone['distance'], 2)} km @ {zone['pace_zone']} Pace"

    if compliance_score > 50:
        score_text = (
            f"Congrats, {round(compliance_score, 2)}% of the distance run in "
            f"{dominant_zone['pace_zone']} Pace is equal or below the associated heart-rate."
        )
    else:
        score_text = (
            f"Be careful, {round(compliance_score, 2)}% of the distance run in "
            f"{dominant_zone['pace_zone']} Pace is above the associated heart-rate."
        )

    return {
        "dominant_zones": dominant_zones,
        "compliance_score": compliance_score,
        "analysis_text": analysis_text,
        "score_text": score_text,
    }
