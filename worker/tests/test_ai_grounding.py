from ai_fixtures import load_cases, snapshot_for

from app.services.ai.grounding import activity_limits, grounded_snapshot, period_limits


def test_limits_distinguish_eligible_blocks_intervals_and_unknown_hr_without_inventing_fatigue():
    cases = {
        case.id: snapshot_for(case.id)
        for case in load_cases()
        if case.kind == "activity"
    }
    steady = activity_limits(cases["activity-controlled"].context)
    assert len(steady.valid_steady_block_decoupling) == 1
    assert steady.valid_steady_block_decoupling[0].decoupling_percent == 0
    intervals = activity_limits(cases["activity-intervals"].context)
    assert (
        intervals.contains_recovery_laps and not intervals.valid_steady_block_decoupling
    )
    missing = activity_limits(cases["activity-missing"].context)
    assert (
        not missing.heart_rate_available and not missing.valid_steady_block_decoupling
    )
    assert not any(
        activity_limits(case.context).fatigue_or_recovery_state_measured
        for case in cases.values()
    )


def test_grounding_changes_only_versioned_model_instructions_preserving_identity_facts_and_caps():
    original = snapshot_for("activity-controlled")
    grounded = grounded_snapshot(original)
    assert grounded.context == original.context and grounded.claim == original.claim
    assert grounded.revision == original.revision and grounded.completion_limit == 2048
    assert grounded.user_prompt == original.user_prompt
    assert grounded.prompt_fingerprint != original.prompt_fingerprint
    assert grounded.prompt_version == "7-g3"


def test_period_limits_supply_exact_percentage_unknown_coverage_and_combined_cycling_load():
    contexts = {
        case.id: snapshot_for(case.id)
        for case in load_cases()
        if case.kind in {"week", "month"}
    }
    month = period_limits(contexts["month-boundary"].context)
    assert month.distance_change_percent["Run"] == (132000 / 105000 - 1) * 100
    recovery = period_limits(contexts["week-recovery"].context)
    assert (
        recovery.current_all_sport_minutes,
        recovery.previous_all_sport_minutes,
    ) == (672, 132)
    assert recovery.current_sport_duration_hms == {"Run": "2:12:00", "Ride": "9:00:00"}
    assert recovery.previous_sport_duration_hms == {"Run": "2:12:00"}
    missing = period_limits(contexts["month-incomplete"].context)
    assert missing.unknown_hr_seconds["Run"] == 1320
    assert (missing.covered_dates, missing.total_dates) == (15, 30)
    assert (missing.previous_covered_dates, missing.previous_total_dates) == (0, 31)
    incomplete = period_limits(contexts["week-incomplete"].context)
    assert (incomplete.previous_covered_dates, incomplete.previous_total_dates) == (
        0,
        7,
    )
    assert grounded_snapshot(contexts["month-boundary"]).prompt_version == "5-g3"


def test_incomplete_calendar_coverage_requires_conservative_advice_without_changing_complete_windows():
    for case in load_cases():
        if case.kind not in {"week", "month"}:
            continue
        original = snapshot_for(case.id)
        revised = grounded_snapshot(original)
        incomplete = (
            original.context.date_coverage.covered_days
            < original.context.date_coverage.period_days
        )
        assert revised.prompt_version == ("5-g4-incomplete" if incomplete else "5-g3")
        assert revised.user_prompt == original.user_prompt
        assert revised.context == original.context and revised.completion_limit == 2048
