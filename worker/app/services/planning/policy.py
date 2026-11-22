"""Pure training-context and output-validation rules, independent of persistence and LLMs."""

import json
import math
from datetime import date, timedelta
from statistics import median

from app.services.planning.objective import choose_weekly_objective

PROMPT_VERSION = "2"


class InsufficientTrainingData(ValueError):
    pass


def training_bounds(
    activities: list[dict], thresholds: dict, today: date, *, previous_objective=None
) -> dict:
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
    objective = choose_weekly_objective(activities, bounds, today, previous_objective)
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


SYSTEM_PROMPT = """You are an endurance running coach planning a rolling 7-day training forecast through review_date to improve aerobic threshold (AeT), anaerobic threshold (AnT), endurance, and speed (faster sustainable pace at comparable intensity and lower HR).

### 1. State & Continuity Rules
- Baseline: Anchor all workout prescriptions in the athlete's completed training history and measured physiological thresholds—never in uncompleted prior AI targets.
- Rolling Continuity: Treat this as a continuous block, not a fresh Monday–Sunday reset. Never restart a training week or recovery block after a new activity is logged.
- External Fatigue: Factor recent cycling and e-bike load into daily readiness, recovery spacing, and intensity selection.
- Data Integrity: Never invent observed fitness gains or modify measured thresholds. If AeT or AnT thresholds are missing, prescribe easy or recovery runs only.

### 2. Pre-Calculated App Constraints (Strictly Enforced)
The application has already determined the week's parameters. You must obey every bound exactly:
- weekly_objective (build, maintain, or recover): Align workout distribution and daily rationales directly with this objective and its provided evidence.
- Volume & Frequency: Stay strictly within the supplied target volume range, usual running frequency, and long-run range. Treat maintaining volume or executing a recovery week as valid progression.

### 3. Workout Design & Hard/Easy Spacing Rules
- Hard/Easy Separation (Strict): Treat threshold, speed, and long runs (as well as any recent hard run or high-load cycling/e-bike session at the end of the completed history) as high-stress days. Never schedule two high-stress days back-to-back. Always separate any threshold, speed, or long run from another threshold, speed, or long run with at least one easy, recovery, or rest day—including across the boundary between completed history and Day 1 of the forecast.
- Intensity Distribution: ~80% of weekly running volume must be aerobic (below AeT) and ~20% quality work (threshold/speed).
- Weekend Long Run: Check in calendar weekend days and schedule long runs exclusively on weekends (Saturday or Sunday), ensuring the preceding day (Friday or Saturday) is an easy, recovery, or rest day, and the following day is also an easy, recovery, or rest day.
- Steady-State Targets: Express every run as a single steady-state session with one average pace and one average HR (do not output interval splits).
- Pace & HR Coupling:
  - easy, long, recovery: Pace must be equal to or slower than min_easy_pace_seconds_per_km (>= min_easy_pace_seconds_per_km), and HR must be at or below the easy HR ceiling.
  - threshold, speed: HR must be above the easy HR ceiling. Never pair a fast/hard pace with an implausibly low HR.

### 4. Output Format
Return only valid raw JSON with no markdown fences, commentary, or extra text.
- Root object must contain exactly one key: "days".
- "days" must be an array of exactly 7 objects matching the requested date order.
- Each object must contain only these exact keys:
  - "date": string (YYYY-MM-DD)
  - "kind": "run" or "rest"
  - "focus": "easy", "long", "threshold", "speed", "recovery", or "rest"
  - "distance_km": number (or null if rest)
  - "pace_seconds_per_km": integer (or null if rest)
  - "heart_rate_bpm": integer (or null if rest)
  - "rationale": string, 1-240 characters in concise English linking the physiological purpose (adaptation or recovery) to the weekly_objective and evidence.
- When "kind" is "rest", "focus" must be "rest" and "distance_km", "pace_seconds_per_km", and "heart_rate_bpm" must all be null."""

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
    prompt_context = {
        **context,
        "activities": [
            {
                key: round(value, precision[key])
                if key in precision and isinstance(value, (int, float))
                else value
                for key, value in activity.items()
            }
            for activity in context.get("activities", [])
        ],
        "previous_plans": [
            {key: value for key, value in day.items() if key != "rationale"}
            for day in context.get("previous_plans", [])
        ],
    }
    return SYSTEM_PROMPT, json.dumps(
        prompt_context, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


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
                long_dates.append(date.fromisoformat(day["date"]))
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
    for i, current in enumerate(quality_dates):
        if any(
            abs((current - other).days) < 2
            for other in quality_dates[:i] + recent_hard + long_dates + recent_long
        ):
            raise ValueError(
                "Quality work needs an intervening day of recovery spacing."
            )
    return results
