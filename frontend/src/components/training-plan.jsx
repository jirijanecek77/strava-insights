import {useEffect, useMemo, useState} from "react";

import {fetchJson} from "../utils/api";
import {buildCalendarDays, buildQuery, formatLocalDateKey} from "../utils/data";
import {formatNumber, formatPaceSeconds} from "../utils/formatters";

export function useTrainingPlans(calendarMonth, enabled = true) {
    const range = useMemo(() => {
        const days = buildCalendarDays(calendarMonth, []);
        return {date_from: formatLocalDateKey(days[0].date), date_to: formatLocalDateKey(days.at(-1).date)};
    }, [calendarMonth]);
    const key = buildQuery(range);
    const [state, setState] = useState(null);
    useEffect(() => {
        if (!enabled) return;
        let active = true;
        let timer;
        const controller = new AbortController();
        async function load() {
            try {
                const payload = await fetchJson(`/training-plans${key}`, {signal: controller.signal});
                if (active) setState({key, payload, error: null});
            } catch (error) {
                if (active) setState((previous) => ({key, payload: previous?.key === key ? previous.payload : null, error: "Running plans could not be loaded."}));
            } finally {
                if (active) timer = setTimeout(load, 15000);
            }
        }
        load();
        return () => {active = false; clearTimeout(timer); controller.abort();};
    }, [key, enabled]);
    if (!enabled) return {payload: null, error: null, loading: false};
    return state?.key === key ? {payload: state.payload, error: state.error, loading: false} : {payload: null, error: null, loading: true};
}

export function TrainingPlanStatus({payload, loading, error}) {
    if (error) return <p className="training-plan-status" role="status">{error}</p>;
    if (loading) return <p className="training-plan-status" role="status">Loading running plans…</p>;
    if (!payload) return null;
    const messages = {
        pending: "Updating your running plan. Existing targets remain visible.",
        generating: "Updating your running plan. Existing targets remain visible.",
        failed: "Your running plan could not be updated. Existing targets remain visible.",
        insufficient_data: payload.message || "More recent running and heart-rate data is needed to plan your training.",
        not_requested: "Your next running plan will be generated after new activities are imported.",
    };
    const message = messages[payload.status];
    return message ? <p className="training-plan-status" role="status">{message}</p> : null;
}

export function PlannedWorkout({plan}) {
    if (!plan) return null;
    return (
        <div className={`training-plan ${plan.stale ? "training-plan-stale" : ""}`}>
            <span className="training-plan-label">Planned{plan.stale ? " · previous" : ""}</span>
            <p>{plan.rationale}</p>
            <div className="training-plan-targets">
                {plan.kind === "rest" ? <span>Rest</span> : <>
                    <strong>{formatNumber(plan.distance_km)} km</strong>
                    <span>{formatPaceSeconds(plan.pace_seconds_per_km).replace(" /km", "")} min/km</span>
                    <span>{plan.heart_rate_bpm} bpm</span>
                </>}
            </div>
        </div>
    );
}
