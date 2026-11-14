import {fireEvent, render, screen} from "@testing-library/react";
import {describe, expect, it, vi} from "vitest";
import {ActivitySplitsChart} from "./activity-splits";

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

const splits = {status: "ready", laps: [
    {number: 1, lap_type: "WARMUP", start_distance_meters: 0, end_distance_meters: 890, distance_meters: 890,
        duration_seconds: 300, average_pace_seconds_per_km: 337, average_speed_kph: 10.68, average_heartrate_bpm: 140},
    {number: 2, lap_type: "INTERVAL", start_distance_meters: 890, end_distance_meters: 1290, distance_meters: 400,
        duration_seconds: 100, average_pace_seconds_per_km: 250, average_speed_kph: 14.4, average_heartrate_bpm: 166,
        elevation_gain_meters: 7.6, elevation_loss_meters: 3.2
    },
]};
const series = {distance_km: [0, 0.5, 0.89, 0.9, 1.29], altitude_meters: [200, 202, 203, 207, 201]};

describe("ActivitySplitsChart", () => {
    it("focuses the original stream index and shows lap averages and current elevation", () => {
        const onSelectIndex = vi.fn();
        render(<ActivitySplitsChart splits={splits} series={series} isRun activeIndex={0} onSelectIndex={onSelectIndex}/>);
        expect(screen.queryByText("Avg pace (min/km)")).not.toBeInTheDocument();
        expect(screen.queryByText("Elevation (m)")).not.toBeInTheDocument();
        fireEvent.mouseMove(screen.getByRole("button", {name: "Focus split"}));
        expect(onSelectIndex).toHaveBeenCalledWith(3);
        expect(screen.getByText("Split 2 · interval")).toBeInTheDocument();
        expect(screen.queryByText("0.89–1.29 km")).not.toBeInTheDocument();
        expect(screen.getByText("Time: 1:40")).toBeInTheDocument();
        expect(screen.getByLabelText("Split net elevation change")).toHaveTextContent("Net: +4 m");
        expect(screen.getByText("Avg pace: 4:10 /km")).toBeInTheDocument();
        expect(screen.getByText("Avg HR: 166 bpm")).toBeInTheDocument();
        expect(screen.getByText("Elevation: 207 m")).toBeInTheDocument();
        expect(screen.getByText("↑ 8 m / ↓ 3 m")).toBeInTheDocument();
    });

    it("labels ordinary active laps as splits without exposing the provider's active type", () => {
        const activeSplits = {...splits, laps: splits.laps.map((lap) => ({...lap, lap_type: "ACTIVE"}))};
        render(<ActivitySplitsChart splits={activeSplits} series={series} isRun activeIndex={0}/>);
        fireEvent.mouseMove(screen.getByRole("button", {name: "Focus split"}));
        expect(screen.getByText("Split 2")).toBeInTheDocument();
        expect(screen.queryByText(/active/i)).not.toBeInTheDocument();
    });

    it("reflects external focus, shows ride speed, and works without elevation or HR", () => {
        const noHR = {
            ...splits, laps: splits.laps.map((lap) => ({
                ...lap, average_heartrate_bpm: null,
                elevation_gain_meters: null, elevation_loss_meters: null
            }))
        };
        const {rerender} = render(<ActivitySplitsChart splits={noHR} series={{...series, altitude_meters: []}} isRun={false} activeIndex={0}/>);
        expect(screen.getByTestId("lap-focus")).toHaveTextContent("0–0.89");
        rerender(<ActivitySplitsChart splits={noHR} series={{...series, altitude_meters: []}} isRun={false} activeIndex={3}/>);
        expect(screen.getByTestId("lap-focus")).toHaveTextContent("0.89–1.29");
        fireEvent.mouseMove(screen.getByRole("button", {name: "Focus split"}));
        expect(screen.getByText("Avg speed: 14.4 km/h")).toBeInTheDocument();
        expect(screen.queryByText(/Elevation:/)).not.toBeInTheDocument();
        expect(screen.queryByText(/↑|↓/)).not.toBeInTheDocument();
        expect(screen.queryByText("Avg HR (bpm)")).not.toBeInTheDocument();
    });

    it("uses Garmin totals without an elevation stream and preserves zero and missing values independently", () => {
        const partial = {
            ...splits, laps: splits.laps.map((lap) => ({
                ...lap,
                elevation_gain_meters: 0, elevation_loss_meters: null
            }))
        };
        render(<ActivitySplitsChart splits={partial} series={{...series, altitude_meters: []}} isRun activeIndex={3}/>);
        fireEvent.mouseMove(screen.getByRole("button", {name: "Focus split"}));
        expect(screen.getByLabelText("Split ascent and descent")).toHaveTextContent("↑ 0 m / ↓ n/a");
        expect(screen.queryByLabelText("Split net elevation change")).not.toBeInTheDocument();
    });

    it("does not replace absent Garmin totals with stream-derived ascent or descent", () => {
        const oldSplits = {
            ...splits, laps: splits.laps.map((lap) => ({
                ...lap,
                elevation_gain_meters: undefined, elevation_loss_meters: undefined
            }))
        };
        render(<ActivitySplitsChart splits={oldSplits} series={series} isRun activeIndex={3}/>);
        fireEvent.mouseMove(screen.getByRole("button", {name: "Focus split"}));
        expect(screen.queryByLabelText("Split ascent and descent")).not.toBeInTheDocument();
        expect(screen.queryByLabelText("Split net elevation change")).not.toBeInTheDocument();
        expect(screen.getByText("Elevation: 207 m")).toBeInTheDocument();
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
