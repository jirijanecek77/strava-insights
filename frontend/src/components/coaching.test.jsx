import {render, screen} from "@testing-library/react";
import {describe, expect, it} from "vitest";

import {ActivityCoachingCard, PeriodCoachingPanel} from "./coaching";

describe("ActivityCoachingCard", () => {
    it("renders the summary, description paragraphs, and next-session advice", () => {
        render(
            <ActivityCoachingCard
                coaching={{
                    status: "ready",
                    summary: "Controlled 10 km aerobic run.",
                    description: "You kept the effort easy.\n\nHeart rate stayed below AeT.",
                    recommendation: "Recover tomorrow, then add strides.",
                    model: "gemini-3.8-flash",
                }}
            />,
        );

        expect(screen.getByText("Controlled 10 km aerobic run.")).toBeInTheDocument();
        expect(screen.getByText("You kept the effort easy.")).toBeInTheDocument();
        expect(screen.getByText("Heart rate stayed below AeT.")).toBeInTheDocument();
        expect(screen.getByText("Next session")).toBeInTheDocument();
        expect(screen.getByText("Recover tomorrow, then add strides.")).toBeInTheDocument();
        expect(screen.getByText("gemini-3.8-flash")).toBeInTheDocument();
    });

    it("shows pending and failed states and nothing without a note", () => {
        const {rerender, container} = render(<ActivityCoachingCard coaching={{status: "pending"}}/>);
        expect(screen.getByText(/will be written shortly/i)).toBeInTheDocument();

        rerender(<ActivityCoachingCard coaching={{status: "failed"}}/>);
        expect(screen.getByText(/could not be generated/i)).toBeInTheDocument();

        rerender(<ActivityCoachingCard coaching={null}/>);
        expect(container).toBeEmptyDOMElement();
    });
});

describe("PeriodCoachingPanel", () => {
    it("shows time-weighted percentages for weekly HR bands", () => {
        render(<PeriodCoachingPanel calendarMonth={new Date(2026, 10, 1)} items={[{
            period_type: "week", period_start: "2026-11-02", period_end: "2026-11-08", status: "ready",
            summary: "Mostly aerobic work.", metrics: {
                hr_bands_by_sport: {
                    Run: {
                        bands: {
                            below_aet: {time_s: 3600, distance_m: 10000, time_percent: 75},
                            between_aet_ant: {time_s: 1200, distance_m: 4000, time_percent: 25},
                            above_ant: {time_s: 0, distance_m: 0, time_percent: 0}
                        },
                        coverage: {unknown_time_s: 0, unknown_distance_m: 0}, threshold_definitions: [],
                    }
                }
            },
        }]}/>);
        expect(screen.getByRole("columnheader", {name: "% time"})).toBeInTheDocument();
        expect(screen.getByText("75.0%")).toBeInTheDocument();
        expect(screen.getByText("25.0%")).toBeInTheDocument();
        expect(screen.getByText("0.0%")).toBeInTheDocument();
    });

    it("shows the month review first and weeks newest first", () => {
        render(
            <PeriodCoachingPanel
                calendarMonth={new Date(2026, 9, 1)}
                items={[
                    {period_type: "week", period_start: "2026-09-28", period_end: "2026-10-04", status: "ready", summary: "Older week.", recommendation: "Rest.", is_final: true},
                    {period_type: "week", period_start: "2026-10-05", period_end: "2026-10-11", status: "ready", summary: "Current week.", recommendation: "Go long.", is_final: false},
                    {period_type: "month", period_start: "2026-10-01", period_end: "2026-10-31", status: "pending", is_final: false},
                ]}
            />,
        );

        const headings = screen.getAllByRole("heading", {level: 3}).map((heading) => heading.textContent);
        expect(headings[0]).toMatch(/October 2026/);
        expect(headings[1]).toMatch(/^Week 41/);
        expect(headings[2]).toMatch(/^Week 40/);
        expect(screen.getByText("In progress")).toBeInTheDocument();
        expect(screen.getByText("Rest of the week")).toBeInTheDocument();
        expect(screen.getByText("Next week")).toBeInTheDocument();
        expect(screen.getByText(/this review will be written shortly/i)).toBeInTheDocument();
    });

    it("shows measured bands and unclassified coverage, preserving unavailable values", () => {
        render(<PeriodCoachingPanel calendarMonth={new Date(2026, 9, 1)} items={[{
            period_type: "month", period_start: "2026-10-01", period_end: "2026-10-31", status: "ready",
            summary: "Limited HR coverage.", metrics: {hr_bands_by_sport: {Run: {
                bands: {below_aet: {time_s: 3661, distance_m: 12345}, between_aet_ant: {time_s: 0, distance_m: 0},
                    above_ant: {time_s: null, distance_m: null}},
                coverage: {unknown_time_s: 600, unknown_distance_m: 1000}, threshold_definitions: [{}, {}],
            }}},
        }]}/>);
        expect(screen.getByRole("table", {name: "Run heart-rate threshold totals"})).toBeInTheDocument();
        expect(screen.getByText("1:01:01")).toBeInTheDocument();
        expect(screen.getByText("12.35 km")).toBeInTheDocument();
        expect(screen.getByText("0.00 km")).toBeInTheDocument();
        expect(screen.getAllByText("Unavailable")).toHaveLength(2);
        expect(screen.getByText(/Unclassified: 0:10:00/)).toBeInTheDocument();
        expect(screen.getByText(/Threshold definitions changed/)).toBeInTheDocument();
    });

    it("renders nothing when there are no reviews", () => {
        const {container} = render(<PeriodCoachingPanel calendarMonth={new Date(2026, 9, 1)} items={[]}/>);
        expect(container).toBeEmptyDOMElement();
    });
});
