import {describe, expect, it} from "vitest";

import {computeDetailTooltipPosition, resolveDetailChartPresentation} from "./data";

describe("resolveDetailChartPresentation", () => {
    it("excludes only abnormal endpoint speed values while preserving an interior interval value", () => {
        const values = [0.1, 10, 10.2, 0.2, 9.8, 10.1, 10.3, 9.9, 0.3];

        const presentation = resolveDetailChartPresentation({valueKind: "speed", values});

        expect(presentation.domainValues).toEqual([10, 10.2, 0.2, 9.8, 10.1, 10.3, 9.9]);
        expect(presentation.presentationValues).toEqual([null, 10, 10.2, 0.2, 9.8, 10.1, 10.3, 9.9, null]);
    });

    it("excludes pace extrema only when they occur at an endpoint", () => {
        const values = [0.1, 5, 5.2, 16, 4.9, 5.1, 5.3, 5.1, 16];

        const presentation = resolveDetailChartPresentation({valueKind: "pace", values});

        expect(presentation.domainValues).toEqual([5, 5.2, 16, 4.9, 5.1, 5.3, 5.1]);
        expect(presentation.presentationValues).toEqual([null, 5, 5.2, 16, 4.9, 5.1, 5.3, 5.1, null]);
    });

    it("preserves a short series because there is no reliable baseline for filtering", () => {
        const values = [0.1, 5, 16];

        const presentation = resolveDetailChartPresentation({valueKind: "pace", values});

        expect(presentation.domainValues).toEqual(values);
        expect(presentation.presentationValues).toEqual(values);
    });
});

describe("computeDetailTooltipPosition", () => {
    it("keeps tooltips inside the chart at vertical and horizontal extremes", () => {
        const common = {maxValue: 180, minValue: 60, xMax: 10, xMin: 0};

        expect(computeDetailTooltipPosition({
            ...common,
            activePoint: {distance: 0, value: 180},
            valueKind: "heart_rate",
        })).toMatchObject({horizontalAnchor: "left", verticalPlacement: "below"});
        expect(computeDetailTooltipPosition({
            ...common,
            activePoint: {distance: 10, value: 60},
            valueKind: "heart_rate",
        })).toMatchObject({horizontalAnchor: "right", verticalPlacement: "above"});
        expect(computeDetailTooltipPosition({
            maxValue: 6,
            minValue: 4,
            xMax: 10,
            xMin: 0,
            activePoint: {distance: 5, value: 4},
            valueKind: "pace",
        })).toMatchObject({horizontalAnchor: "center", verticalPlacement: "below"});
    });
});
