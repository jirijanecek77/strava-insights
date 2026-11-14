"""Deterministic, reusable coaching evidence. No network or model dependencies."""

import hashlib
import json
from math import isfinite
from statistics import median

VERSION = 3
BANDS = ("below_aet", "between_aet_ant", "above_ant")


def number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if isfinite(result) else None
    except (ValueError, TypeError):
        return None


def values(stream, name):
    return list((getattr(stream, name, None) or {}).get("data", []) or [])


def fingerprint(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def threshold_values(profile):
    aet = number(getattr(profile, "aet_heart_rate_bpm", None))
    ant = number(getattr(profile, "ant_heart_rate_bpm", None))
    if aet is None or ant is None or not 0 < aet < ant:
        return None
    return {
        "aet_hr_bpm": aet,
        "ant_hr_bpm": ant,
        "effective_from": str(getattr(profile, "effective_from", "unknown")),
    }


def band_totals(activity, stream, thresholds):
    times = values(stream, "time_stream")
    distances = values(stream, "distance_stream")
    hrs = values(stream, "heartrate_stream")
    totals = {band: {"time_s": 0.0, "distance_m": 0.0} for band in BANDS}
    time_coverage = distance_coverage = 0.0
    has_distance = False
    limitations = [
        "Moving status unavailable; zero-distance intervals and gaps over 60s are excluded."
    ]
    if thresholds:
        for i in range(1, min(len(times), len(hrs))):
            previous, current, hr = (
                number(times[i - 1]),
                number(times[i]),
                number(hrs[i]),
            )
            if (
                previous is None
                or current is None
                or hr is None
                or hr <= 0
                or not 0 < current - previous <= 60
            ):
                continue
            delta = None
            if i < len(distances):
                d0, d1 = number(distances[i - 1]), number(distances[i])
                if d0 is not None and d1 is not None:
                    if d0 < 0 or d1 < d0:
                        continue
                    delta = d1 - d0
                    if delta == 0:
                        continue
            band = (
                "below_aet"
                if hr < thresholds["aet_hr_bpm"]
                else "between_aet_ant" if hr < thresholds["ant_hr_bpm"] else "above_ant"
            )
            totals[band]["time_s"] += current - previous
            time_coverage += current - previous
            if delta is not None:
                totals[band]["distance_m"] += delta
                distance_coverage += delta
                has_distance = True
    else:
        limitations.append("Valid dated AeT/AnT HR thresholds unavailable.")
    total_time = max(0, number(activity.moving_time_seconds) or 0)
    total_distance = max(0, number(activity.distance_meters) or 0)
    if time_coverage > total_time + 1 or distance_coverage > total_distance + 1:
        limitations.append(
            "Measured coverage exceeds activity totals; totals are not rescaled."
        )
    coverage = {
        "classified_time_s": time_coverage,
        "classified_distance_m": distance_coverage,
        "unknown_time_s": max(0, total_time - time_coverage),
        "unknown_distance_m": max(0, total_distance - distance_coverage),
    }
    for row in totals.values():
        if not time_coverage:
            row["time_s"] = None
        if not has_distance:
            row["distance_m"] = None
    return {"bands": totals, "coverage": coverage, "limitations": limitations}


def terrain_section(stream, start_m, end_m):
    """20m sampling, 3m ascent/descent hysteresis, reject >40% grade spikes/gaps."""
    points = []
    for distance, altitude in zip(
        values(stream, "distance_stream"), values(stream, "altitude_stream")
    ):
        d, a = number(distance), number(altitude)
        if d is not None and a is not None and start_m <= d <= end_m:
            if not points or d - points[-1][0] >= 20:
                points.append((d, a))
    ascent = descent = covered = net = 0.0
    anchor = None
    for previous, current in zip(points, points[1:]):
        length, height = current[0] - previous[0], current[1] - previous[1]
        if not 0 < length <= 200 or abs(height / length) > 0.4:
            anchor = None
            continue
        covered += length
        net += height
        if anchor is None:
            anchor = previous[1]
        if abs(current[1] - anchor) >= 3:
            change = current[1] - anchor
            ascent += max(0, change)
            descent += max(0, -change)
            anchor = current[1]
    coverage = covered / (end_m - start_m) if end_m > start_m else 0
    return {
        "start_distance_m": round(start_m, 1),
        "end_distance_m": round(end_m, 1),
        "coverage_fraction": round(min(1, coverage), 3),
        "ascent_m": round(ascent, 1) if covered else None,
        "descent_m": round(descent, 1) if covered else None,
        "net_change_m": round(net, 1) if covered else None,
        "net_grade_pct": round(net * 100 / covered, 2) if covered else None,
    }


def lap_evidence(laps, stream, thresholds, sport):
    """Summarize continuous steady work; retain work/recovery separation."""
    terrain = []
    groups = []
    group = []
    group_kind = None
    position = 0.0
    for lap in laps:
        distance = number(lap.get("distance_meters")) or 0
        start = number(lap.get("start_distance_meters"))
        start = position if start is None else start
        end = start + distance
        position = end
        section = terrain_section(stream, start, end)
        # Recorded totals are independent of stream coverage. Never replace missing Garmin totals with estimates.
        for field, stored_field in (
                ("ascent_m", "elevation_gain_meters"),
                ("descent_m", "elevation_loss_meters"),
        ):
            value = number(lap.get(stored_field))
            section[field] = value if value is not None and value >= 0 else None
        section["elevation_totals_source"] = (
            "garmin"
            if section["ascent_m"] is not None or section["descent_m"] is not None
            else "unavailable"
        )
        section["lap"] = lap["number"]
        terrain.append(section)
        duration, hr = number(lap.get("duration_seconds")), number(
            lap.get("average_heartrate_bpm")
        )
        kind = None
        lap_type = str(lap.get("lap_type") or "").upper()
        if (
            sport == "Run"
            and thresholds
            and duration
            and distance > 0
            and hr
            and lap_type not in {"RECOVERY", "REST", "WARMUP", "COOLDOWN"}
        ):
            if hr < thresholds["aet_hr_bpm"]:
                kind = "endurance"
            elif hr < thresholds["ant_hr_bpm"]:
                kind = "tempo"
        if kind != group_kind or kind is None:
            if group:
                groups.append((group_kind, group))
            group = []
        if kind:
            group.append(
                {
                    "lap": lap["number"],
                    "time_s": duration,
                    "distance_m": distance,
                    "hr_bpm": hr,
                    "terrain": section,
                }
            )
        group_kind = kind
    if group:
        groups.append((group_kind, group))
    candidates = {"endurance": [], "tempo": []}
    for kind, rows in groups:
        duration = sum(row["time_s"] for row in rows)
        distance = sum(row["distance_m"] for row in rows)
        paces = [row["time_s"] * 1000 / row["distance_m"] for row in rows]
        if (
            duration < (1200 if kind == "endurance" else 480)
            or max(paces) / min(paces) > 1.10
            or max(row["hr_bpm"] for row in rows) - min(row["hr_bpm"] for row in rows)
            > 10
        ):
            continue
        complete_terrain = all(
            row["terrain"]["coverage_fraction"] >= 0.8 for row in rows
        )
        complete_totals = all(
            row["terrain"]["ascent_m"] is not None
            and row["terrain"]["descent_m"] is not None
            for row in rows
        )
        decoupling = None
        if kind == "endurance":
            from app.services.coaching.metrics import aerobic_decoupling_percent

            time_values = values(stream, "time_stream")
            distance_values = values(stream, "distance_stream")
            hr_values = values(stream, "heartrate_stream")
            start_m, end_m = (
                rows[0]["terrain"]["start_distance_m"],
                rows[-1]["terrain"]["end_distance_m"],
            )
            samples = [
                (time, length, hr)
                for time, length, hr in zip(time_values, distance_values, hr_values)
                if number(length) is not None and start_m <= length <= end_m
            ]
            # Use only a continuous, well-covered steady block, not whole-session interval decoupling.
            valid_times = [number(row[0]) for row in samples]
            if (
                complete_terrain
                    and complete_totals
                    # Raw pace/HR decoupling is meaningful only on nearly flat work.
                    # GAP is deliberately not approximated from a whole-lap net grade.
                    and all(abs(row["terrain"]["net_grade_pct"]) <= 0.5 for row in rows)
                    and sum(
                row["terrain"]["ascent_m"] + row["terrain"]["descent_m"]
                for row in rows
            )
                    * 1000
                    / distance
                    <= 10
                and samples
                and all(time is not None for time in valid_times)
                and all(
                    number(row[2]) is not None and number(row[2]) > 0 for row in samples
                )
                and all(
                    0 < right - left <= 60
                    for left, right in zip(valid_times, valid_times[1:])
                )
                and valid_times[-1] - valid_times[0] >= duration * 0.8
                    and valid_times[-1] - valid_times[0] <= duration * 1.05
                    and all(right[1] > left[1] for left, right in zip(samples, samples[1:]))
                    and _steady_speed(samples)
            ):
                decoupling = aerobic_decoupling_percent(
                    time_seconds=[row[0] for row in samples],
                    distance_meters=[row[1] for row in samples],
                    heartrate_bpm=[row[2] for row in samples],
                )
        candidates[kind].append(
            {
                "lap_range": [rows[0]["lap"], rows[-1]["lap"]],
                "start_distance_m": rows[0]["terrain"]["start_distance_m"],
                "end_distance_m": rows[-1]["terrain"]["end_distance_m"],
                "duration_s": duration,
                "distance_m": distance,
                "pace_s_per_km": duration * 1000 / distance,
                "decoupling_pct": decoupling,
                "hr_bpm": sum(row["hr_bpm"] * row["time_s"] for row in rows) / duration,
                "efficiency_m_per_beat": distance
                                         * 60
                                         / sum(row["hr_bpm"] * row["time_s"] for row in rows),
                "net_grade_pct": (
                    (
                        sum(
                            row["terrain"]["net_grade_pct"] * row["distance_m"]
                            for row in rows
                        )
                        / distance
                    )
                    if complete_terrain
                    else None
                ),
                "ascent_m_per_km": (
                    sum(row["terrain"]["ascent_m"] for row in rows) * 1000 / distance
                    if all(row["terrain"]["ascent_m"] is not None for row in rows)
                    else None
                ),
                "limitations": [
                    "Lap averages cannot establish within-lap effort or workout intent."
                ],
            }
        )
    # A bounded reusable digest; never propagate full lap arrays into period prompts.
    candidates = {
        kind: sorted(rows, key=lambda row: row["duration_s"], reverse=True)[:3]
        for kind, rows in candidates.items()
    }
    return terrain, candidates


def _steady_speed(samples):
    """Reject hidden work/recovery changes using rolling minute speeds, not lap averages."""
    left = 0
    speeds = []
    for right in range(1, len(samples)):
        while left + 1 < right and samples[right][0] - samples[left + 1][0] >= 60:
            left += 1
        duration = samples[right][0] - samples[left][0]
        if duration >= 60:
            speeds.append((samples[right][1] - samples[left][1]) / duration)
    return bool(speeds) and min(speeds) > 0 and max(speeds) / min(speeds) <= 1.2


def build_evidence(activity, stream, recorded, profile, route_group_id=None):
    thresholds = threshold_values(profile)
    laps = (
        recorded.laps
        if recorded is not None
        and recorded.status == "ready"
        and activity.source_provider == "garmin"
        else []
    )
    lap_terrain, candidates = lap_evidence(
        laps, stream, thresholds, activity.sport_type
    )
    distance = max(0, number(activity.distance_meters) or 0)
    local = activity.start_date_local or activity.start_date_utc
    return {
        "schema_version": VERSION,
        "activity_id": activity.id,
        "date": local.date().isoformat(),
        "sport": activity.sport_type,
        "route_group_id": route_group_id,
        "threshold_snapshot": thresholds,
        "volume": {
            "distance_m": distance,
            "moving_time_s": number(activity.moving_time_seconds) or 0,
        },
        "hr_bands": band_totals(activity, stream, thresholds),
        "terrain": {
            "total_ascent_m": number(activity.total_elevation_gain_meters),
            "laps": lap_terrain,
            "finish": terrain_section(stream, distance * 0.8, distance),
            "limitation": "Terrain aggregates are approximate; missing coverage is not flat terrain.",
        },
        "candidates": candidates,
    }


def aggregate_evidence(evidence):
    sports = {}
    for item in evidence:
        row = sports.setdefault(
            item["sport"],
            {
                "activities": 0,
                "bands": {band: {"time_s": None, "distance_m": None} for band in BANDS},
                "coverage": {key: 0.0 for key in item["hr_bands"]["coverage"]},
                "limitations": [],
                "activities_missing_hr": 0,
                "threshold_definitions": [],
            },
        )
        for limitation in item["hr_bands"]["limitations"]:
            if limitation not in row["limitations"]:
                row["limitations"].append(limitation)
        row["activities"] += 1
        if item["hr_bands"]["bands"]["below_aet"]["time_s"] is None:
            row["activities_missing_hr"] += 1
        threshold = item["threshold_snapshot"]
        if threshold and threshold not in row["threshold_definitions"]:
            row["threshold_definitions"].append(threshold)
        for band in BANDS:
            for unit in ("time_s", "distance_m"):
                value = item["hr_bands"]["bands"][band][unit]
                if value is not None:
                    row["bands"][band][unit] = (row["bands"][band][unit] or 0) + value
        for key, value in item["hr_bands"]["coverage"].items():
            row["coverage"][key] += value
    return sports


def compare_performance(current, previous):
    result = {}
    for kind in ("endurance", "tempo"):
        pairs = []
        used = set()
        # Match across the period, one independent session on each side per pair.
        for item in sorted(current, key=lambda row: row["date"]):
            match = None
            for candidate in item["candidates"][kind]:
                for old in previous:
                    if (
                        old["activity_id"] in used
                        or item["sport"] != "Run"
                        or old["sport"] != "Run"
                    ):
                        continue
                    if item["threshold_snapshot"] != old["threshold_snapshot"]:
                        continue
                    same_route = (
                        item["route_group_id"] is not None
                        and item["route_group_id"] == old["route_group_id"]
                    )
                    for baseline in old["candidates"][kind]:
                        if (
                            abs(candidate["hr_bpm"] - baseline["hr_bpm"]) > 5
                            or not 0.8
                            <= candidate["duration_s"] / baseline["duration_s"]
                            <= 1.2
                        ):
                            continue
                        terrain_ok = (
                            candidate["net_grade_pct"] is not None
                            and baseline["net_grade_pct"] is not None
                            and abs(
                                candidate["net_grade_pct"] - baseline["net_grade_pct"]
                            )
                            <= 1
                            and abs(
                                candidate["ascent_m_per_km"]
                                - baseline["ascent_m_per_km"]
                            )
                            <= 10
                        )
                        has_terrain = (
                            candidate["net_grade_pct"] is not None
                            and baseline["net_grade_pct"] is not None
                        )
                        # Identical lap numbers/distance offsets on a matched loop do
                        # not prove the same physical terrain (manual/auto laps vary).
                        if not has_terrain or not terrain_ok:
                            continue
                        score = (
                            not same_route,
                            abs(candidate["hr_bpm"] - baseline["hr_bpm"]),
                        )
                        if match is None or score < match[0]:
                            match = (score, old, baseline, candidate)
            if match:
                _, old, baseline, candidate = match
                used.add(old["activity_id"])
                pairs.append(
                    {
                        "current_activity_id": item["activity_id"],
                        "previous_activity_id": old["activity_id"],
                        "current_date": item["date"],
                        "previous_date": old["date"],
                        "current": candidate,
                        "previous": baseline,
                        "pace_change_pct": (
                            candidate["pace_s_per_km"] / baseline["pace_s_per_km"] - 1
                        )
                        * 100,
                        "duration_change_pct": (
                            candidate["duration_s"] / baseline["duration_s"] - 1
                        )
                        * 100,
                        "decoupling_change_pp": (
                            (candidate["decoupling_pct"] - baseline["decoupling_pct"])
                            if candidate.get("decoupling_pct") is not None
                            and baseline.get("decoupling_pct") is not None
                            else None
                        ),
                    }
                )
        pace = median(pair["pace_change_pct"] for pair in pairs) if pairs else None
        duration = (
            median(pair["duration_change_pct"] for pair in pairs) if pairs else None
        )
        drifts = [
            pair["decoupling_change_pp"]
            for pair in pairs
            if pair["decoupling_change_pp"] is not None
        ]
        drift = median(drifts) if len(drifts) >= 2 else None
        status = "insufficient_data"
        if len(pairs) >= 2:
            status = (
                "improving"
                if pace <= -2
                or (
                    kind == "endurance"
                    and pace <= 1
                    and (duration >= 10 or (drift is not None and drift <= -2))
                )
                else "declining" if pace >= 2 else "stable"
            )
        result[kind] = {
            "status": status,
            "matched_pairs": len(pairs),
            "median_pace_change_pct": pace,
            "median_duration_change_pct": duration,
            "median_decoupling_change_pp": drift,
            "evidence": (
                [pairs[0], pairs[len(pairs) // 2], pairs[-1]]
                if len(pairs) > 3
                else pairs
            ),
            "limitations": [
                "At least two independent matched session pairs required for a trend.",
                "Lap averages do not establish workout intent; weather and fatigue can confound comparisons.",
            ],
        }
    return result
