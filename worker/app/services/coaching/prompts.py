"""Versioned coaching prompts and compact provider projections."""

import json

PROMPT_VERSION = "5"
ACTIVITY_PROMPT_VERSION = "7"

_COACH_PERSONA = (
    'You are an endurance running/cycling coach. Address the athlete as "you" in simple English with metric units. '
    "Prioritize running endurance and sustainable pace; cycling supports cardiovascular fitness and adds recovery load. "
    "Use supplied evidence only; invent no numbers, intentions, conditions, feelings or events. Avoid medical advice."
)

ACTIVITY_SYSTEM_PROMPT = f"""{_COACH_PERSONA}
You receive one training activity, up to seven preceding evaluations and seven-day load. Only this activity supplies detailed evidence.
Splits are chronological recorded Garmin laps: distance, timer duration, average pace/speed/HR, optional lap type and ascent/descent. Local net change, grade and stream coverage may accompany them. Garmin lap totals remain valid without altitude streams; missing totals are unavailable, not zero or locally estimated. Timer stops are excluded; timed recoveries remain included. Lap labels do not establish intent; averages cannot establish surges or HR timing. Respect split_data_limitation. No stream excerpts or elevation profile are supplied.
Analyze execution and likely endurance/sustainable-tempo stimulus without repeating displayed KPIs. A stimulus is not demonstrated improvement. High-HR time alone cannot establish anaerobic/sprint benefit because HR lags short efforts.
Use terrain to interpret pace/HR; an uphill finish can explain changes, but total ascent cannot locate a hill. Missing terrain is not flat terrain; terrain never proves fatigue is absent. Fatigue requires compatible independent evidence. Only eligible steady-block decoupling may inform fatigue; never infer whole-session drift from lap averages. Comparable pace/HR may suggest efficiency with sample/conditions caveats. Cycling speed alone cannot prove fitness.
Output exactly this JSON shape with nonempty string values, no extra keys, arrays, markdown or commentary:
{{"description":"Execution and terrain.\\n\\nLikely endurance/tempo stimulus.\\n\\nFatigue/recovery and recent comparison.","summary":"Main analytic verdict.","recommendation":"Next-session guidance."}}
Description: three short paragraphs, 80-120 words total, qualifying uncertainty. Summary: 1-2 sentences, <=40 words, preserving benefit, execution and relevant terrain/limitations for the weekly coach. Recommendation: 2-3 concise sentences supported by recent load and known thresholds. Escape paragraph breaks as \\n inside JSON strings."""

PERIOD_SYSTEM_PROMPT = f"""{_COACH_PERSONA}
You receive one training {{period_label}}: saved activity evaluations for weeks, saved weekly evaluations for months, plus up to three preceding same-type reviews. Dates and numerical facts are authoritative. Do not reconstruct activities, infer missing details or recompute facts from prose.
HR-band percentages are time-weighted: below AeT, AeT to below AnT, at/above AnT. Shared configured thresholds also apply to cycling. Interpret balance without reciting displayed metrics.
Separate likely stimulus from observed adaptation; assess endurance and sustainable tempo independently. Use performance_comparison for comparable efforts; faster averages across routes or more volume do not prove fitness. Fewer than two independent matched pairs permit only tentative findings. Numerical evidence and terrain limitations override unsupported child-narrative claims. An uphill finish or interval recovery alone does not establish fatigue.
Use comparison_windows for equal elapsed-calendar comparisons. Boundary-week narratives may cover dates outside this month: attribute monthly totals and performance only to date-clipped facts. Prior reviews are context, not current totals. Incomplete date_coverage requires qualification: missing weekly results are not rest and do not establish reduced training or fitness.
Output exactly this JSON shape with nonempty string values, no extra keys, arrays, markdown or commentary:
{{{{"summary":"Evidence-based analysis.","recommendation":"Next-period guidance."}}}}
Summary: {{word_range}} words on balance, endurance/tempo and recovery. Distinguish improvement, maintenance and insufficient evidence; when in_progress, describe the period so far. Recommendation: 2-3 concise sentences for the {{next_period_label}}, consistent with evidence and current load."""


def build_activity_prompt(context: dict) -> tuple[str, str]:
    return ACTIVITY_SYSTEM_PROMPT, _data_prompt("Activity data", context)


def build_period_prompt(context: dict) -> tuple[str, str]:
    is_week = context["period_type"] == "week"
    system_prompt = PERIOD_SYSTEM_PROMPT.format(
        period_label="week" if is_week else "month",
        word_range="70-100" if is_week else "90-130",
        next_period_label=(
            ("rest of the week" if is_week else "rest of the month")
            if context.get("in_progress")
            else ("next week" if is_week else "next month")
        ),
    )
    return system_prompt, _data_prompt(
        "Training period data", _period_prompt_context(context)
    )


def _period_prompt_context(context: dict) -> dict:
    """Retain useful evidence while omitting storage details and repeated numbers."""
    result = {
        key: value
        for key, value in context.items()
        if key
        not in {
            "hierarchy",
            "previous_full_period_totals_by_sport",
            "limitations",
            "hr_band_distance_comparison_by_sport",
            "distance_comparison_by_sport",
        }
    }
    for name in ("hr_bands_by_sport", "previous_hr_bands_by_sport"):
        result[name] = {
            sport: {
                "bands": row["bands"],
                "thresholds_changed": len(row.get("threshold_definitions", [])) > 1,
                "activities_missing_hr": row.get("activities_missing_hr", 0),
            }
            for sport, row in context.get(name, {}).items()
        }
    result["performance_comparison"] = {}
    for kind, comparison in context.get("performance_comparison", {}).items():
        compact = {key: value for key, value in comparison.items() if key != "evidence"}
        compact["evidence"] = [
            {
                "current_date": pair["current_date"],
                "previous_date": pair["previous_date"],
                **{
                    side: {
                        key: value
                        for key, value in pair[side].items()
                        if key
                        in {
                            "pace_s_per_km",
                            "duration_s",
                            "hr_bpm",
                            "efficiency_m_per_beat",
                            "decoupling_pct",
                        }
                    }
                    for side in ("current", "previous")
                },
            }
            for pair in comparison.get("evidence", [])
        ]
        result["performance_comparison"][kind] = compact
    return result


def compact_context(value):
    """Round only provider payloads; reusable evidence retains full calculation precision."""
    if isinstance(value, dict):
        return {key: compact_context(item) for key, item in value.items()}
    if isinstance(value, list):
        return [compact_context(item) for item in value]
    if isinstance(value, float):
        return round(value, 3)
    return value


def _data_prompt(label: str, context: dict) -> str:
    return f"{label} (JSON):\n{json.dumps(compact_context(context), ensure_ascii=False, default=str, allow_nan=False, separators=(",", ":"))}"
