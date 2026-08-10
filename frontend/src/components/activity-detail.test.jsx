import {describe, expect, it, vi} from "vitest";

import {createMapyCzMap} from "./activity-detail";

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
