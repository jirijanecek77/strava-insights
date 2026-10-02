import {describe, expect, it} from "vitest";

import {
    buildActivityFilterRule,
    filterActivities,
    formatActivityFilterRule,
    resolveAvailableFilterKpis,
} from "./activity-filters";

const run = {
    id: 1,
    name: "Morning Run",
    distance_km: "10.04",
    moving_time_seconds: 2700,
    total_elevation_gain_meters: "100.00",
    average_heartrate_bpm: "150.00",
    summary_metric_kind: "pace",
    average_pace_seconds_per_km: "270.00",
    average_speed_kph: "13.32",
    aerobic_efficiency_m_per_beat: 1.48,
};
const ride = {
    id: 2,
    name: "Evening Ride",
    distance_km: "42.50",
    moving_time_seconds: 5400,
    total_elevation_gain_meters: "420.00",
    average_heartrate_bpm: null,
    summary_metric_kind: "speed",
    average_pace_seconds_per_km: null,
    average_speed_kph: "28.30",
    aerobic_efficiency_m_per_beat: null,
};

describe("filterActivities", () => {
    it("matches the name case-insensitively anywhere in the name", () => {
        expect(filterActivities([run, ride], {name: "  rUN "})).toEqual([run]);
    });

    it("combines KPI rules with AND", () => {
        const rules = [
            buildActivityFilterRule("distance", "gt", "5"),
            buildActivityFilterRule("moving_time", "lt", "60"),
        ];
        expect(filterActivities([run, ride], {rules})).toEqual([run]);
    });

    it("compares equality at displayed precision", () => {
        expect(filterActivities([run], {rules: [buildActivityFilterRule("distance", "eq", "10")]})).toEqual([run]);
        expect(filterActivities([run], {rules: [buildActivityFilterRule("moving_time", "eq", "45")]})).toEqual([run]);
    });

    it("excludes activities that miss the filtered KPI", () => {
        expect(filterActivities([run, ride], {rules: [buildActivityFilterRule("heart_rate", "lt", "200")]})).toEqual([run]);
    });

    it("filters by efficiency at two-decimal precision", () => {
        expect(filterActivities([run, ride], {rules: [buildActivityFilterRule("efficiency", "eq", "1.48")]})).toEqual([run]);
        expect(filterActivities([run, ride], {rules: [buildActivityFilterRule("efficiency", "gt", "1.5")]})).toEqual([]);
    });

    it("applies pace only to pace activities and speed only to speed activities", () => {
        expect(filterActivities([run, ride], {rules: [buildActivityFilterRule("pace", "lt", "5:00")]})).toEqual([run]);
        expect(filterActivities([run, ride], {rules: [buildActivityFilterRule("speed", "gt", "10")]})).toEqual([ride]);
    });
});

describe("buildActivityFilterRule", () => {
    it("parses pace as m:ss or decimal minutes and rejects invalid input", () => {
        expect(buildActivityFilterRule("pace", "eq", "4:30").value).toBe(270);
        expect(buildActivityFilterRule("pace", "eq", "4.5").value).toBe(270);
        expect(buildActivityFilterRule("distance", "gt", "10,5").value).toBe(10.5);
        expect(buildActivityFilterRule("distance", "gt", "abc")).toBeNull();
        expect(buildActivityFilterRule("distance", "gt", "")).toBeNull();
    });

    it("formats rules for chips", () => {
        expect(formatActivityFilterRule(buildActivityFilterRule("pace", "lt", "4.5"))).toBe("Pace < 4:30 min/km");
        expect(formatActivityFilterRule(buildActivityFilterRule("distance", "gt", "10"))).toBe("Distance > 10 km");
    });
});

describe("resolveAvailableFilterKpis", () => {
    it("offers pace or speed depending on the loaded sports", () => {
        const ids = (activities) => resolveAvailableFilterKpis(activities).map((kpi) => kpi.id);
        expect(ids([run])).toContain("pace");
        expect(ids([run])).not.toContain("speed");
        expect(ids([ride])).toContain("speed");
        expect(ids([ride])).not.toContain("pace");
        expect(ids([run, ride])).toEqual(expect.arrayContaining(["pace", "speed"]));
    });
});
