import {fireEvent, render, screen} from "@testing-library/react";
import {describe, expect, it, vi} from "vitest";

vi.mock("recharts", () => {
    const Wrapper = ({children}) => <div>{children}</div>;
    return {
        ResponsiveContainer: Wrapper,
        ComposedChart: ({children, onMouseMove}) => <div onMouseMove={() => onMouseMove({activeLabel: 0.9})}><svg>{children}</svg><button>Focus split</button></div>,
        ReferenceArea: ({x1, x2}) => <text data-testid="lap-focus">{x1}–{x2}</text>,
        Area: () => null, CartesianGrid: () => null, Line: () => null, ReferenceLine: () => null,
        Tooltip: () => null, XAxis: () => null, YAxis: () => null,
    };
});

import {ActivitySplitsChart} from "./activity-splits";

const splits = {status: "ready", laps: [
    {number: 1, lap_type: "WARMUP", start_distance_meters: 0, end_distance_meters: 890, distance_meters: 890,
        duration_seconds: 300, average_pace_seconds_per_km: 337, average_speed_kph: 10.68, average_heartrate_bpm: 140},
    {number: 2, lap_type: "INTERVAL", start_distance_meters: 890, end_distance_meters: 1290, distance_meters: 400,
        duration_seconds: 100, average_pace_seconds_per_km: 250, average_speed_kph: 14.4, average_heartrate_bpm: 166},
]};
const series = {distance_km: [0, 0.5, 0.89, 0.9, 1.29], altitude_meters: [200, 202, 203, 204, 205]};

describe("ActivitySplitsChart", () => {
    it("focuses the original stream index and shows lap averages and current elevation", () => {
        const onSelectIndex = vi.fn();
        render(<ActivitySplitsChart splits={splits} series={series} isRun activeIndex={0} onSelectIndex={onSelectIndex}/>);
        expect(screen.queryByText("Avg pace (min/km)")).not.toBeInTheDocument();
        expect(screen.queryByText("Elevation (m)")).not.toBeInTheDocument();
        fireEvent.mouseMove(screen.getByRole("button", {name: "Focus split"}));
        expect(onSelectIndex).toHaveBeenCalledWith(3);
        expect(screen.getByText("Lap 2 · interval")).toBeInTheDocument();
        expect(screen.getByText("Avg pace: 4:10 /km")).toBeInTheDocument();
        expect(screen.getByText("Avg HR: 166 bpm")).toBeInTheDocument();
        expect(screen.getByText("Elevation: 204 m")).toBeInTheDocument();
    });

    it("reflects external focus, shows ride speed, and works without elevation or HR", () => {
        const noHR = {...splits, laps: splits.laps.map((lap) => ({...lap, average_heartrate_bpm: null}))};
        const {rerender} = render(<ActivitySplitsChart splits={noHR} series={{...series, altitude_meters: []}} isRun={false} activeIndex={0}/>);
        expect(screen.getByTestId("lap-focus")).toHaveTextContent("0–0.89");
        rerender(<ActivitySplitsChart splits={noHR} series={{...series, altitude_meters: []}} isRun={false} activeIndex={3}/>);
        expect(screen.getByTestId("lap-focus")).toHaveTextContent("0.89–1.29");
        fireEvent.mouseMove(screen.getByRole("button", {name: "Focus split"}));
        expect(screen.getByText("Avg speed: 14.4 km/h")).toBeInTheDocument();
        expect(screen.queryByText(/Elevation:/)).not.toBeInTheDocument();
        expect(screen.queryByText("Avg HR (bpm)")).not.toBeInTheDocument();
    });

    it("shows unavailable splits without suggesting a historical refresh", () => {
        const {rerender} = render(<ActivitySplitsChart series={series} isRun activeIndex={0}/>);
        expect(screen.getByText(/No usable recorded splits/)).toBeInTheDocument();
        expect(screen.queryByText(/Refresh activities/)).not.toBeInTheDocument();
        rerender(<ActivitySplitsChart splits={{status: "pending", laps: []}} series={series} isRun activeIndex={0}/>);
        expect(screen.getByText(/No usable recorded splits/)).toBeInTheDocument();
        rerender(<ActivitySplitsChart splits={{status: "unavailable", laps: []}} series={series} isRun activeIndex={0}/>);
        expect(screen.getByText(/No usable recorded splits/)).toBeInTheDocument();
    });
});
