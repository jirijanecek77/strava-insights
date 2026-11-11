import {describe, expect, it} from "vitest";
import {buildSplitChartData, closestSplitStreamIndex, splitAtDistance} from "./activity-splits";

const laps = [
    {number: 1, start_distance_meters: 0, end_distance_meters: 890.58, distance_meters: 890.58, average_pace_seconds_per_km: 300, average_speed_kph: 12, average_heartrate_bpm: 140},
    {number: 2, start_distance_meters: 890.58, end_distance_meters: 1290.58, distance_meters: 400, average_pace_seconds_per_km: 240, average_speed_kph: 15, average_heartrate_bpm: 165},
    {number: 3, start_distance_meters: 1290.58, end_distance_meters: 1290.58, distance_meters: 0, average_pace_seconds_per_km: null},
    {number: 4, start_distance_meters: 1290.58, end_distance_meters: 1300.58, distance_meters: 10, average_pace_seconds_per_km: 480, average_speed_kph: 7.5, average_heartrate_bpm: null},
];

describe("recorded split chart data", () => {
    it("keeps exact boundaries and both sides of each step through elevation sampling", () => {
        const distance = Array.from({length: 10000}, (_, i) => i / 5000);
        const data = buildSplitChartData(laps, distance, distance.map((d) => 200 + d), true);
        expect(data.filter((p) => p.distance === 0.89058).map((p) => p.metric)).toEqual([5, 4]);
        expect(data.filter((p) => p.distance === 1.29058).map((p) => p.metric)).toEqual([4, 8]);
        expect(data.at(-1)).toMatchObject({distance: 1.30058, metric: 8});
        expect(data.length).toBeLessThan(260);
        expect(data[0].altitude).toBe(200);
    });

    it("uses speed for rides and leaves missing measurements as gaps", () => {
        const data = buildSplitChartData(laps, [], [], false);
        expect(data[0]).toMatchObject({metric: 12, altitude: null});
        expect(data.filter((p) => p.distance === 0.89058).map((p) => p.metric)).toEqual([12, 15]);
        expect(data.at(-1).altitude).toBeNull();
    });

    it("maps distances to the containing lap and original stream indices", () => {
        expect(splitAtDistance(laps, 0.9).number).toBe(2);
        expect(splitAtDistance(laps, 1.29058).number).toBe(4);
        expect(splitAtDistance(laps, 1.30058).number).toBe(4);
        expect(splitAtDistance(laps, 1.5)).toBeNull();
        expect(closestSplitStreamIndex([0, null, 0.89, 0.9, 1.3], 0.9)).toBe(3);
        expect(closestSplitStreamIndex([], 0.9)).toBe(-1);
    });
});
