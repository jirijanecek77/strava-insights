import {fireEvent, render, screen, waitFor} from "@testing-library/react";
import {describe, expect, it, vi} from "vitest";

import {ActivityTitle, createMapyCzMap} from "./activity-detail";
import {ActivitySplitsChart} from "./activity-splits";

it("renders filled pace steps with gray elevation on the right and HR only in the tooltip", async () => {
    const {container} = render(<ActivitySplitsChart isRun activeIndex={0} series={{distance_km: [0, 0.5, 1], altitude_meters: [200, 210, 205]}}
        splits={{status: "ready", laps: [{number: 1, start_distance_meters: 0, end_distance_meters: 1000, distance_meters: 1000,
            average_pace_seconds_per_km: 300, average_heartrate_bpm: 145}]}}/>);
    await waitFor(() => {
        const labels = container.querySelectorAll('.recharts-yAxis-tick-labels text[orientation="left"]');
        expect(labels.length).toBeGreaterThan(0);
        labels.forEach((label) => expect(Number(label.getAttribute("x"))).toBeGreaterThanOrEqual(0));
        expect(container.querySelector('.recharts-yAxis-tick-labels text[orientation="right"]')).toHaveTextContent(/m$/);
        expect(container.querySelectorAll('.recharts-area-area')).toHaveLength(2);
        expect(container.querySelector('.recharts-line-curve')).toBeNull();
    });
});

describe("createMapyCzMap", () => {
    it("initializes bounds before attaching segmented route layers", () => {
        const calls = [];
        const map = {
            fitBounds: vi.fn(() => calls.push("fitBounds")),
            invalidateSize: vi.fn(),
            on: vi.fn(),
            remove: vi.fn(),
        };
        const routeLayer = {
            addTo: vi.fn(() => {
                calls.push("routeLayer");
                return routeLayer;
            }),
            on: vi.fn(),
        };
        const activeMarker = {
            addTo: vi.fn(() => activeMarker),
            setLatLng: vi.fn(),
        };
        const attribution = {
            addAttribution: vi.fn(),
            addTo: vi.fn(),
        };
        const L = {
            circleMarker: vi.fn(() => activeMarker),
            control: {attribution: vi.fn(() => attribution)},
            latLngBounds: vi.fn(() => ({isValid: () => true})),
            map: vi.fn(() => map),
            polyline: vi.fn(() => routeLayer),
            tileLayer: vi.fn(() => ({addTo: vi.fn()})),
        };

        const instance = createMapyCzMap(
            {L, tileConfig: {attribution: "Mapy.com", maxZoom: 18, minZoom: 0, tileSize: 256, urlTemplate: "tiles"}},
            document.createElement("div"),
            [[50, 14], [50.01, 14.01], [50.02, 14.02]],
            [0, 1, 2],
            [0, 1],
            vi.fn(),
        );

        expect(instance).not.toBeNull();
        expect(calls).toEqual(["fitBounds", "routeLayer"]);
        expect(L.polyline).toHaveBeenCalledTimes(1);
        expect(L.polyline).toHaveBeenCalledWith(
            [[50.01, 14.01], [50.02, 14.02]],
            {color: "#fc4c02", opacity: 0.95, weight: 3},
        );

        instance.destroy();
        expect(map.remove).toHaveBeenCalledOnce();
    });
});

describe("ActivityTitle", () => {
    it("edits the name inline, keeps editing on save error, and cancels on Escape", async () => {
        const onRenameActivity = vi.fn().mockRejectedValue(new Error("Activity not found."));
        render(<ActivityTitle activityId={11} name="Morning Run" onRenameActivity={onRenameActivity}/>);

        fireEvent.click(screen.getByRole("button", {name: /rename activity/i}));
        const input = screen.getByLabelText(/activity name/i);
        expect(input).toHaveFocus();
        fireEvent.change(input, {target: {value: "   "}});
        expect(screen.getByRole("button", {name: /save name/i})).toBeDisabled();

        fireEvent.change(input, {target: {value: "Evening Run"}});
        fireEvent.click(screen.getByRole("button", {name: /save name/i}));
        expect(await screen.findByRole("alert")).toHaveTextContent("Activity not found.");
        expect(onRenameActivity).toHaveBeenCalledWith(11, "Evening Run");
        expect(screen.getByLabelText(/activity name/i)).toBeInTheDocument();

        fireEvent.keyDown(screen.getByLabelText(/activity name/i), {key: "Escape"});
        expect(screen.queryByLabelText(/activity name/i)).not.toBeInTheDocument();
        expect(screen.getByRole("heading", {name: "Morning Run"})).toBeInTheDocument();
    });
});
