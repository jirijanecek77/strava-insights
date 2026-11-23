"""Pure training-context and output-validation rules, independent of persistence and LLMs."""

import json
import math
from app.services.planning.objective import choose_weekly_objective
from datetime import date, timedelta
from statistics import median

PROMPT_VERSION = "3"


class InsufficientTrainingData(ValueError):
    pass


def training_bounds(activities: list[dict], thresholds: dict, today: date) -> dict:
    runs = [
        a
        for a in activities
        if a["sport"] == "Run" and a["distance_km"] > 0 and a["pace_seconds_per_km"]
    ]
    if len(runs) < 3 or not any(
        date.fromisoformat(a["date"]) >= today - timedelta(days=14) for a in runs
    ):
        raise InsufficientTrainingData(
            "At least three recent runs, including one in the last 14 days, are needed."
        )
    hr_samples = [a["hr_bpm"] for a in runs if a["hr_bpm"]]
    if not hr_samples and not thresholds.get("aet_heart_rate_bpm"):
        raise InsufficientTrainingData(
            "Running heart-rate history or an aerobic HR threshold is needed."
        )
    weekly = []
    frequencies = []
    long_distances = []
    for week in range(6):
        end = today - timedelta(days=7 * week)
        start = end - timedelta(days=6)
        block = [a for a in runs if start <= date.fromisoformat(a["date"]) <= end]
        weekly.append(round(sum(a["distance_km"] for a in block), 2))
        frequencies.append(len({a["date"] for a in block}))
        long_distances.append(max((a["distance_km"] for a in block), default=0))
    # Use recent four-week capacity; the older two weeks provide trend context, not a higher load ceiling.
    baseline = max(weekly[:4])
    if baseline <= 0:
        raise InsufficientTrainingData(
            "Recent running volume is too low to establish a plan."
        )
    recent_runs = [
        a for a in runs if date.fromisoformat(a["date"]) >= today - timedelta(days=27)
    ]
    aet = thresholds.get("aet_heart_rate_bpm")
    ant = thresholds.get("ant_heart_rate_bpm")
    hard_dates = []
    for a in activities:
        if a["hr_bpm"] and (
            (aet and a["hr_bpm"] > aet) or (ant and a["hr_bpm"] >= ant)
        ):
            hard_dates.append(a["date"])
    observed_hr = round(median(hr_samples)) if hr_samples else aet
    all_sport_minutes = [
        sum(
            a.get("moving_minutes", 0)
            for a in activities
            if today - timedelta(days=7 * week + 6)
            <= date.fromisoformat(a["date"])
            <= today - timedelta(days=7 * week)
        )
        for week in range(5)
    ]
    prior_active_minutes = [value for value in all_sport_minutes[1:] if value > 0]
    prior_minutes = median(prior_active_minutes) if prior_active_minutes else 0
    recent_hard_days = {
        d for d in hard_dates if date.fromisoformat(d) >= today - timedelta(days=6)
    }
    recovery_load_spike = (
        prior_minutes > 0 and all_sport_minutes[0] > prior_minutes * 1.30
    ) or len(recent_hard_days) >= 3
    typical_volume = median([value for value in weekly[:4] if value > 0])
    bounds = {
        "weekly_distances_km": weekly,
        "weekly_running_days": frequencies,
        "weekly_long_distances_km": long_distances,
        "typical_weekly_distance_km": typical_volume,
        "recent_all_sport_minutes": all_sport_minutes,
        "recovery_load_spike": recovery_load_spike,
        "max_weekly_distance_km": round(baseline * 1.10, 2),
        "max_run_distance_km": round(
            max(a["distance_km"] for a in recent_runs) * 1.10, 2
        ),
        "max_running_days": min(6, max(frequencies[:4]) + 1),
        "max_quality_days": (
            2
            if aet
            and ant
            and any(
                date.fromisoformat(a["date"]) >= today - timedelta(days=6) for a in runs
            )
            else 0
        ),
        "min_easy_pace_seconds_per_km": (
            round(thresholds["aet_pace_min_per_km"] * 60)
            if thresholds.get("aet_pace_min_per_km")
            else round(median(a["pace_seconds_per_km"] for a in recent_runs))
        ),
        "min_easy_distance_share": 0.70,
        "min_pace_seconds_per_km": max(
            120, round(min(a["pace_seconds_per_km"] for a in recent_runs) * 0.90)
        ),
        "max_pace_seconds_per_km": min(
            1200, round(max(a["pace_seconds_per_km"] for a in recent_runs) * 1.5)
        ),
        "easy_hr_ceiling_bpm": aet or observed_hr,
        "max_hr_bpm": min(220, ant + 5) if ant else observed_hr,
        "recent_hard_dates": hard_dates,
        "recent_long_dates": [
            a["date"]
            for a in recent_runs
            if a["distance_km"] >= max(x["distance_km"] for x in recent_runs) * 0.9
        ],
    }
    objective = choose_weekly_objective(activities, bounds, today)
    bounds.update(
        weekly_objective=objective,
        min_weekly_distance_km=objective["distance_min_km"],
        max_weekly_distance_km=objective["distance_max_km"],
        max_running_days=objective["target_running_days"],
        min_running_days=(
            max(1, objective["target_running_days"] - 1)
            if objective["mode"] != "recover"
            else 0
        ),
        min_long_run_distance_km=objective["long_run_min_km"],
        max_run_distance_km=objective["long_run_max_km"],
        min_quality_days=(
            1
            if objective["mode"] == "build"
            and bounds["max_quality_days"]
            and objective["target_running_days"] >= 4
            else 0
        ),
    )
    if objective["mode"] == "recover":
        bounds["max_quality_days"] = 0
    return bounds


SYSTEM_PROMPT = """You are an endurance running coach. Plan the seven requested dates from completed training and current AeT/AnT thresholds to improve endurance and sustainable speed. Cycling/e-bike load contributes to recovery. Never invent fitness gains or change measured thresholds.
Follow every supplied bound and the freshly computed weekly_objective (build/maintain/recover). Do not carry over earlier AI targets. Historical aggregates may cover 42 days; individual activities cover 30. Missing coaching_summary means no saved interpretation: use numerical evidence and acknowledge uncertainty.
Use weekdays in the same order as dates. Long runs are allowed only on Sat/Sun. Separate every threshold, speed or long run from other such sessions and recent hard/long activities by at least one easy/recovery/rest day, including the completed-history boundary.
Keep at least min_easy_distance_share of distance easy. Without both HR thresholds use easy/recovery only. Easy/long/recovery pace >= min_easy_pace_seconds_per_km and HR <= easy_hr_ceiling_bpm. Threshold/speed HR must exceed that ceiling. Use one steady distance, average pace and HR per run, no interval splits.
Return ONLY valid JSON, no markdown or commentary. Root has exactly one key "days": an array of exactly seven objects in requested date order. Each object has exactly the seven keys shown below. Replace example values with supported targets and requested dates. No extra keys, NaN, trailing commas, ranges or units inside numbers.
Run example: {"date":"2026-11-14","kind":"run","focus":"long","distance_km":12.5,"pace_seconds_per_km":345,"heart_rate_bpm":140,"rationale":"Easy endurance volume supports the current objective."}
Rest example: {"date":"2026-11-15","kind":"rest","focus":"rest","distance_km":null,"pace_seconds_per_km":null,"heart_rate_bpm":null,"rationale":"Recover from the preceding long run."}
Allowed run focus: easy,long,threshold,speed,recovery. Distance is a positive number; pace and HR are integers. A rest day has focus rest and all three targets null. Rationale is a concise English string of 1-240 characters explaining purpose from supplied evidence."""


def build_prompt(context: dict) -> tuple[str, str]:
    # Project only the provider payload: persisted context and validation retain full precision.
    # Applying this here also trims contexts already saved for pending/retried requests.
    precision = {
        "distance_km": 2,
        "moving_minutes": 1,
        "elevation_gain_meters": 0,
        "pace_seconds_per_km": 0,
        "hr_bpm": 0,
    }
    today = date.fromisoformat(context.get("today", context["dates"][0]))
    since = (today - timedelta(days=29)).isoformat()
    prompt_context = {
        **{key: value for key, value in context.items() if key != "previous_plans"},
        "weekdays": [
            ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")[
                date.fromisoformat(d).weekday()
            ]
            for d in context["dates"]
        ],
        "activities": [
            {
                key: (
                    round(value, precision[key])
                    if key in precision and isinstance(value, (int, float))
                    else value
                )
                for key, value in activity.items()
            }
            for activity in context.get("activities", [])
            if since <= activity["date"] <= today.isoformat()
        ],
    }
    user_prompt = json.dumps(
        prompt_context, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return SYSTEM_PROMPT, user_prompt


def validate_plan(payload: dict, context: dict) -> list[dict]:
    if (
        set(payload) != {"days"}
        or not isinstance(payload["days"], list)
        or len(payload["days"]) != 7
    ):
        raise ValueError("Expected exactly seven planned days.")
    bounds = context["bounds"]
    results, quality_dates, long_dates = [], [], []
    total, easy, running_days = 0.0, 0.0, 0
    longest = 0.0
    expected_fields = {
        "date",
        "kind",
        "focus",
        "distance_km",
        "pace_seconds_per_km",
        "heart_rate_bpm",
        "rationale",
    }
    for index, day in enumerate(payload["days"]):
        if (
            not isinstance(day, dict)
            or set(day) != expected_fields
            or day["date"] != context["dates"][index]
        ):
            raise ValueError("Plan dates/fields do not match the requested window.")
        if (
            not isinstance(day["rationale"], str)
            or not 1 <= len(day["rationale"].strip()) <= 240
        ):
            raise ValueError("Each day needs a short training rationale.")
        if day["kind"] == "rest":
            if day["focus"] != "rest" or any(
                day[k] is not None
                for k in ("distance_km", "pace_seconds_per_km", "heart_rate_bpm")
            ):
                raise ValueError("Rest days must have no run targets.")
        elif day["kind"] == "run":
            if day["focus"] not in {"easy", "long", "threshold", "speed", "recovery"}:
                raise ValueError("Unknown running focus.")
            distance, pace, hr = (
                day["distance_km"],
                day["pace_seconds_per_km"],
                day["heart_rate_bpm"],
            )
            if (
                type(distance) not in (int, float)
                or not math.isfinite(distance)
                or not 0 < distance <= bounds["max_run_distance_km"]
            ):
                raise ValueError("Run distance exceeds recent long-run capacity.")
            if (
                type(pace) is not int
                or not bounds["min_pace_seconds_per_km"]
                <= pace
                <= bounds["max_pace_seconds_per_km"]
            ):
                raise ValueError("Pace is outside the athlete's supported range.")
            if type(hr) is not int or not 80 <= hr <= bounds["max_hr_bpm"]:
                raise ValueError("Heart-rate target is outside the supported range.")
            is_quality = (
                day["focus"] in {"threshold", "speed"}
                or hr > bounds["easy_hr_ceiling_bpm"]
            )
            if (
                day["focus"] in {"easy", "long", "recovery"}
                and hr > bounds["easy_hr_ceiling_bpm"]
            ):
                raise ValueError(
                    "Aerobic/recovery runs must stay at or below the easy HR ceiling."
                )
            if is_quality:
                if hr <= bounds["easy_hr_ceiling_bpm"]:
                    raise ValueError(
                        "Quality sessions need a heart-rate target above the easy ceiling."
                    )
                quality_dates.append(date.fromisoformat(day["date"]))
            else:
                if pace < bounds["min_easy_pace_seconds_per_km"]:
                    raise ValueError(
                        "Easy sessions must not be faster than the aerobic pace baseline."
                    )
                easy += distance
            if day["focus"] == "long":
                long_date = date.fromisoformat(day["date"])
                if long_date.weekday() < 5:
                    raise ValueError("Long runs must be scheduled on a weekend.")
                long_dates.append(long_date)
            running_days += 1
            total += distance
            longest = max(longest, distance)
        else:
            raise ValueError("Unknown day kind.")
        results.append(day)
    if (
        total > bounds["max_weekly_distance_km"] + 0.001
        or running_days > bounds["max_running_days"]
    ):
        raise ValueError("Plan exceeds recent volume/frequency capacity.")
    if total + 0.001 < bounds["min_weekly_distance_km"]:
        raise ValueError(
            f"Planned distance {total:g} km is below the weekly objective minimum of {bounds['min_weekly_distance_km']:g} km; retain easy mileage while respecting recovery spacing."
        )
    if (
        running_days < bounds["min_running_days"]
        or longest + 0.001 < bounds["min_long_run_distance_km"]
    ):
        raise ValueError(
            "Plan omits the running frequency or long-run distance required by the weekly objective."
        )
    if len(quality_dates) < bounds["min_quality_days"]:
        raise ValueError("The build objective requires a purposeful quality session.")
    if len(quality_dates) > bounds["max_quality_days"] or (
        total and easy / total < bounds["min_easy_distance_share"]
    ):
        raise ValueError("Plan contains too much quality work.")
    recent_hard = [date.fromisoformat(d) for d in bounds["recent_hard_dates"]]
    recent_long = [date.fromisoformat(d) for d in bounds["recent_long_dates"]]
    demanding_dates = sorted(quality_dates + long_dates)
    for i, current in enumerate(demanding_dates):
        if any(
            abs((current - other).days) < 2
            for other in demanding_dates[:i] + recent_hard + recent_long
        ):
            raise ValueError(
                "Quality work and long runs need an intervening day of recovery spacing."
            )
    return results
