import {render, screen} from "@testing-library/react";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";

import {CalendarView} from "./views";

const plan = {planned_date: "2026-12-01", kind: "run", focus: "easy", distance_km: 10, pace_seconds_per_km: 330, heart_rate_bpm: 145, rationale: "Build aerobic endurance.", stale: true};

function renderCalendar(selectedSport = "", activities = [{
    id: 5,
    sport_type: "Run",
    start_date_local: "2026-12-01T10:00:00",
    distance_km: 8
}]) {
    return render(<CalendarView calendarMonth={new Date(2026, 10, 1)} activities={activities} onChangeMonth={() => {
    }} onSelectActivity={() => {
    }} selectedSport={selectedSport}/>);
}

beforeEach(() => {
    vi.useFakeTimers({toFake: ["Date"]});
    vi.setSystemTime(new Date(2026, 11, 1, 23, 30));
});

afterEach(() => {vi.useRealTimers(); vi.restoreAllMocks();});

describe("calendar running plans", () => {
    it("hides past run and rest targets while keeping today, future targets, and completed activities", async () => {
        vi.setSystemTime(new Date(2026, 11, 2, 0, 30));
        vi.spyOn(global, "fetch").mockResolvedValue({ok: true, status: 200, json: async () => ({status: "ready", items: [
            {...plan, rationale: "Past run."},
            {...plan, planned_date: "2026-11-30", kind: "rest", rationale: "Past rest."},
            {...plan, planned_date: "2026-12-02", rationale: "Today run."},
            {...plan, planned_date: "2026-12-03", kind: "rest", rationale: "Future rest."},
        ]})});
        renderCalendar();
        expect(await screen.findByText("Today run.")).toBeVisible();
        expect(screen.getByText("Future rest.")).toBeVisible();
        expect(screen.queryByText("Past run.")).not.toBeInTheDocument();
        expect(screen.queryByText("Past rest.")).not.toBeInTheDocument();
        expect(screen.getByRole("button", {name: "8 km, 1 activity"})).toBeInTheDocument();
    });

    it("hides today's suggestion after an activity while keeping future targets and completed activities", async () => {
        const fetch = vi.spyOn(global, "fetch").mockResolvedValue({ok: true, status: 200, json: async () => ({status: "pending", items: [plan, {...plan, planned_date: "2026-12-02", kind: "rest", rationale: "Recover."}]})});
        renderCalendar();
        expect(await screen.findByText("Recover.")).toBeVisible();
        expect(screen.queryByText("5:30 min/km")).not.toBeInTheDocument();
        expect(screen.queryByText("145 bpm")).not.toBeInTheDocument();
        expect(screen.getByText("Rest")).toBeInTheDocument();
        expect(screen.getByRole("button", {name: "8 km, 1 activity"})).toBeInTheDocument();
        expect(screen.getByText(/updating your running plan/i)).toBeInTheDocument();
        expect(fetch.mock.calls[0][0]).toContain("date_from=2026-10-26&date_to=2026-12-06");
        expect(screen.queryByText("Build aerobic endurance.")).not.toBeInTheDocument();
        expect(screen.getByText("Recover.")).toBeVisible();
    });

    it.each(["Ride", "EBikeRide"])("hides today's suggestion after a recorded %s", async (sport) => {
        vi.spyOn(global, "fetch").mockResolvedValue({
            ok: true, status: 200, json: async () => ({
                status: "ready", items: [
                    plan,
                    {...plan, planned_date: "2026-12-02", rationale: "Tomorrow's run."},
                ]
            })
        });
        renderCalendar("", [{id: 6, sport_type: sport, start_date_local: "2026-12-01T23:00:00", distance_km: 8}]);
        expect(await screen.findByText("Tomorrow's run.")).toBeVisible();
        expect(screen.queryByText("Build aerobic endurance.")).not.toBeInTheDocument();
        expect(screen.getByRole("button", {name: "8 km, 1 activity"})).toBeInTheDocument();
    });

    it.each(["run", "rest"])("hides today's %s suggestion when activity is excluded by the running filter", async (kind) => {
        vi.spyOn(global, "fetch").mockResolvedValue({
            ok: true, status: 200, json: async () => ({
                status: "ready", items: [
                    {...plan, kind, has_completed_activity: true, rationale: "Today's suggestion."},
                    {...plan, planned_date: "2026-12-02", has_completed_activity: true, rationale: "Tomorrow's run."},
                ]
            })
        });
        renderCalendar("Run", []);
        expect(await screen.findByText("Tomorrow's run.")).toBeVisible();
        expect(screen.queryByText("Today's suggestion.")).not.toBeInTheDocument();
        expect(screen.getByText("5:30 min/km")).toBeInTheDocument();
        expect(screen.getByText("145 bpm")).toBeInTheDocument();
    });

    it("hides running plans under the cycling filter", async () => {
        const fetch = vi.spyOn(global, "fetch");
        renderCalendar("Ride");
        expect(screen.queryByText(/planned/i)).not.toBeInTheDocument();
        expect(fetch).not.toHaveBeenCalled();
    });

    it("keeps completed activities usable when the plans API fails", async () => {
        vi.spyOn(global, "fetch").mockRejectedValue(new Error("Offline"));
        renderCalendar();
        expect(await screen.findByText(/running plans could not be loaded/i)).toBeInTheDocument();
        expect(screen.getByRole("button", {name: "8 km, 1 activity"})).toBeInTheDocument();
    });
});
