"""Choose a training-block objective from completed work before assigning daily workouts."""

import math
from datetime import date, timedelta
from statistics import median


def assess_aerobic_response(
    activities: list[dict], today: date, easy_hr: float
) -> dict:
    """Compare aerobic runs with earlier runs of similar distance, pace/HR, and available terrain.

    These are possible fatigue indicators, not a physiological diagnosis. A single adverse comparison
    affects session placement; a repeated signal on distinct recent dates can justify a recovery block.
    """
    runs = [
        a
        for a in activities
        if a["sport"] == "Run"
        and a.get("hr_bpm")
        and a.get("pace_seconds_per_km")
        and a["distance_km"] >= 3
        and a["hr_bpm"] <= easy_hr + 5
    ]
    recent = [
        a for a in runs if date.fromisoformat(a["date"]) >= today - timedelta(days=6)
    ]
    reference = [
        a for a in runs if date.fromisoformat(a["date"]) < today - timedelta(days=6)
    ]
    compared, adverse = set(), {}
    for run in recent:
        peers = []
        for other in reference:
            if (
                not 0.70 * run["distance_km"]
                <= other["distance_km"]
                <= 1.30 * run["distance_km"]
            ):
                continue
            if (
                run.get("elevation_gain_meters") is not None
                and other.get("elevation_gain_meters") is not None
            ):
                slope = run["elevation_gain_meters"] / run["distance_km"]
                peer_slope = other["elevation_gain_meters"] / other["distance_km"]
                if abs(slope - peer_slope) > 10:
                    continue
            peers.append(other)
        same_pace = [
            a
            for a in peers
            if abs(a["pace_seconds_per_km"] / run["pace_seconds_per_km"] - 1) <= 0.05
        ]
        same_hr = [a for a in peers if abs(a["hr_bpm"] - run["hr_bpm"]) <= 3]
        # Two reference sessions reduce the chance of treating one unusual run as the baseline.
        if len(same_pace) >= 2:
            compared.add(run["date"])
            typical_hr = median(a["hr_bpm"] for a in same_pace)
            if run["hr_bpm"] >= typical_hr + 5:
                adverse[run["date"]] = (
                    f"{run['date']}: HR {run['hr_bpm']:g} vs {typical_hr:g} bpm at similar pace/distance."
                )
        if len(same_hr) >= 2:
            compared.add(run["date"])
            typical_pace = median(a["pace_seconds_per_km"] for a in same_hr)
            if run["pace_seconds_per_km"] >= typical_pace * 1.05:
                adverse[run["date"]] = (
                    f"{run['date']}: pace {run['pace_seconds_per_km']:g} vs {typical_pace:g} s/km at similar HR/distance."
                )
    return {
        "compared_days": len(compared),
        "adverse_dates": sorted(adverse),
        "evidence": list(adverse.values()),
    }


def choose_weekly_objective(activities, bounds, today, previous=None):
    if not previous or previous.get("mode") not in {"build", "maintain", "recover"}:
        previous = None
    weekly = bounds["weekly_distances_km"]
    typical = bounds["typical_weekly_distance_km"]
    latest = weekly[0]
    runs = [a for a in activities if a["sport"] == "Run" and a["distance_km"] > 0]
    latest_run = max(date.fromisoformat(a["date"]) for a in runs)
    returning = (today - latest_run).days >= 7
    response = assess_aerobic_response(activities, today, bounds["easy_hr_ceiling_bpm"])
    previous_weeks = [value for value in weekly[1:5] if value > 0]
    prior_volume = median(previous_weeks) if previous_weeks else typical
    evidence = list(response["evidence"])
    repeated_fatigue = len(response["adverse_dates"]) >= 2
    recovery_required = returning or repeated_fatigue or bounds["recovery_load_spike"]
    can_build = (
        not recovery_required
        and not response["adverse_dates"]
        and latest <= prior_volume * 1.10
        and len(previous_weeks) >= 3
        and response["compared_days"] >= 2
        and latest >= typical * 0.90
    )
    if returning:
        reason = "Return after a break: rebuild with easy running before restoring quality work."
        evidence.append(f"Last completed run was {(today - latest_run).days} days ago.")
    elif repeated_fatigue:
        reason = (
            "Repeated adverse aerobic pace/HR comparisons support a recovery block."
        )
    elif bounds["recovery_load_spike"]:
        reason = (
            "Recent all-sport load or hard-session density supports a recovery block."
        )
        evidence.append(
            f"All-sport weekly minutes: {bounds['recent_all_sport_minutes']}."
        )
    elif response["adverse_dates"]:
        reason = "Maintain established volume; an isolated fatigue indicator calls for local recovery and moving quality work."
    elif latest > prior_volume * 1.10:
        reason = "Consolidate the recent volume increase before adding more load."
        evidence.append(
            f"Latest running week {latest:g} km vs prior active-week median {prior_volume:g} km."
        )
    elif can_build:
        reason = "Stable comparable aerobic sessions and established volume support modest progression."
    else:
        reason = "Maintain completed training volume while collecting stronger evidence for progression."
    mode = "recover" if recovery_required else ("build" if can_build else "maintain")

    # Carry the block's intent and review date across activity-triggered rolling forecasts.
    # New meaningful fatigue can lower the objective mid-block; one ordinary run cannot restart a week.
    if previous and previous.get("mode") in {"build", "maintain", "recover"}:
        review_date = date.fromisoformat(previous["review_date"])
        if today < review_date and (
            not recovery_required or previous["mode"] == "recover"
        ):
            objective = dict(previous, continued=True)
            objective["current_response"] = response
            return _within_capacity(objective, bounds)
    else:
        review_date = today + timedelta(days=8)
    block_start = (
        previous["block_start"]
        if previous and today < review_date
        else (today + timedelta(days=1)).isoformat()
    )
    if not previous or today >= review_date:
        review_date = today + timedelta(days=8)

    # Completed training establishes the volume anchor. Earlier AI plans never lower it.
    anchor = (latest + typical) / 2 if latest else typical
    target_days = min(
        bounds["max_running_days"],
        max(
            1,
            math.ceil(median([n for n in bounds["weekly_running_days"][:4] if n > 0])),
        ),
    )
    long_reference = (
        bounds["max_run_distance_km"] / 1.10
        + median([n for n in bounds["weekly_long_distances_km"][:4] if n > 0])
    ) / 2
    if mode == "build":
        low, high = max(latest, anchor) * 1.02, max(latest, anchor) * 1.06
        long_low, long_high = long_reference * 0.95, long_reference * 1.10
    elif mode == "maintain":
        low, high = anchor * 0.95, anchor * 1.05
        long_low, long_high = long_reference * 0.90, long_reference * 1.05
    else:
        low, high = (0, typical * 0.60) if returning else (anchor * 0.60, anchor * 0.80)
        long_low, long_high = 0, long_reference * 0.75
        target_days = max(1, target_days - 1)
    objective = {
        "mode": mode,
        "block_start": block_start,
        "review_date": review_date.isoformat(),
        "decision_date": today.isoformat(),
        "continued": False,
        "reason": reason,
        "evidence": evidence,
        "current_response": response,
        "distance_min_km": round(low, 2),
        "distance_max_km": round(high, 2),
        "target_running_days": target_days,
        "long_run_min_km": round(min(long_low, low * 0.45), 2),
        "long_run_max_km": round(long_high, 2),
    }
    return _within_capacity(objective, bounds)


def _within_capacity(objective, bounds):
    objective["target_running_days"] = min(
        objective["target_running_days"], bounds["max_running_days"]
    )
    objective["long_run_max_km"] = min(
        objective["long_run_max_km"], bounds["max_run_distance_km"]
    )
    objective["distance_max_km"] = round(
        min(
            objective["distance_max_km"],
            bounds["max_weekly_distance_km"],
            objective["long_run_max_km"] * objective["target_running_days"],
        ),
        2,
    )
    objective["distance_min_km"] = min(
        objective["distance_min_km"], objective["distance_max_km"]
    )
    objective["target_distance_km"] = round(
        (objective["distance_min_km"] + objective["distance_max_km"]) / 2, 2
    )
    objective["long_run_min_km"] = min(
        objective["long_run_min_km"],
        objective["long_run_max_km"],
        round(objective["distance_min_km"] * 0.45, 2),
    )
    objective["target_running_days"] = min(
        objective["target_running_days"], bounds["max_running_days"]
    )
    return objective
