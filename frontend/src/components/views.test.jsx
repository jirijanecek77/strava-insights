import {fireEvent, render, screen, within} from "@testing-library/react";
import {describe, expect, it} from "vitest";

import {ActivitiesView} from "./views";

const activities = [
    {id: 1, name: "Morning Run", sport_type: "Run", distance_km: "10.00", moving_time_seconds: 2700, summary_metric_kind: "pace", average_pace_seconds_per_km: "270.00"},
    {id: 2, name: "Long Run", sport_type: "Run", distance_km: "21.10", moving_time_seconds: 6300, summary_metric_kind: "pace", average_pace_seconds_per_km: "298.00"},
];

function renderView() {
    return render(
        <ActivitiesView
            activities={activities}
            activeSeriesIndex={null}
            activityDetail={null}
            detailState="idle"
            selectedActivityId={null}
            onSelectSeriesIndex={() => {}}
            onSelectActivity={() => {}}
        />,
    );
}

describe("ActivitiesView filter", () => {
    it("filters by name and KPI rule and clears", () => {
        const {container} = renderView();
        const list = () => container.querySelector(".activity-list");

        fireEvent.change(screen.getByLabelText(/filter by activity name/i), {target: {value: "morning"}});
        expect(within(list()).queryByText("Long Run")).not.toBeInTheDocument();
        expect(screen.getByText("1 / 2")).toBeInTheDocument();

        fireEvent.change(screen.getByLabelText(/filter by activity name/i), {target: {value: ""}});
        fireEvent.change(screen.getByLabelText(/filter kpi/i), {target: {value: "distance"}});
        fireEvent.change(screen.getByLabelText(/filter value/i), {target: {value: "15"}});
        fireEvent.click(screen.getByRole("button", {name: /add filter/i}));

        expect(within(list()).queryByText("Morning Run")).not.toBeInTheDocument();
        expect(within(list()).getByText("Long Run")).toBeInTheDocument();
        expect(screen.getByRole("button", {name: /remove filter distance > 15 km/i})).toBeInTheDocument();

        fireEvent.change(screen.getByLabelText(/filter kpi/i), {target: {value: "distance"}});
        fireEvent.change(screen.getByLabelText(/filter value/i), {target: {value: "50"}});
        fireEvent.click(screen.getByRole("button", {name: /add filter/i}));
        expect(screen.getByText(/no activities match the filter/i)).toBeInTheDocument();

        fireEvent.click(screen.getByRole("button", {name: /^clear$/i}));
        expect(within(list()).getByText("Morning Run")).toBeInTheDocument();
        expect(within(list()).getByText("Long Run")).toBeInTheDocument();
    });

    it("offers pace but not speed for running activities", () => {
        renderView();
        const options = within(screen.getByLabelText(/filter kpi/i)).getAllByRole("option").map((option) => option.textContent);
        expect(options).toContain("Pace");
        expect(options).not.toContain("Speed");
    });
});
