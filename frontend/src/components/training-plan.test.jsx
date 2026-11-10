import {render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import {CalendarView} from "./views";

const plan = {planned_date: "2026-12-01", kind: "run", focus: "easy", distance_km: 10, pace_seconds_per_km: 330, heart_rate_bpm: 145, rationale: "Build aerobic endurance.", stale: true};

function renderCalendar(selectedSport = "") {
    return render(<CalendarView calendarMonth={new Date(2026, 10, 1)} activities={[{id: 5, sport_type: "Run", start_date_local: "2026-12-01T10:00:00", distance_km: 8}]} onChangeMonth={() => {}} onSelectActivity={() => {}} selectedSport={selectedSport}/>);
}

afterEach(() => {vi.restoreAllMocks();});

describe("calendar running plans", () => {
    it("loads the entire visible grid and shows targets alongside completed runs", async () => {
        const fetch = vi.spyOn(global, "fetch").mockResolvedValue({ok: true, status: 200, json: async () => ({status: "pending", items: [plan, {...plan, planned_date: "2026-12-02", kind: "rest", rationale: "Recover."}]})});
        renderCalendar();
        expect(await screen.findByText("5:30 min/km")).toBeInTheDocument();
        expect(screen.getByText("145 bpm")).toBeInTheDocument();
        expect(screen.getByText("Rest")).toBeInTheDocument();
        expect(screen.getByRole("button", {name: "8 km, 1 activity"})).toBeInTheDocument();
        expect(screen.getByText(/updating your running plan/i)).toBeInTheDocument();
        expect(fetch.mock.calls[0][0]).toContain("date_from=2026-10-26&date_to=2026-12-06");
        expect(screen.getByText("Build aerobic endurance.")).toBeVisible();
        expect(screen.getByText("Recover.")).toBeVisible();
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
