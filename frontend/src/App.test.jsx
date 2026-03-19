import {act, fireEvent, render, screen, waitFor} from "@testing-library/react";

import App, {buildThresholdGuides, parseSummaryMetricAverage, resolveDetailReferenceValue} from "./App";

function jsonResponse(body, status = 200) {
    return {
        ok: status >= 200 && status < 300,
        status,
        json: vi.fn().mockResolvedValue(body),
    };
}

describe("App", () => {
    afterEach(() => {
        vi.restoreAllMocks();
    });

    it("renders the login screen when the session is anonymous", async () => {
        vi.spyOn(global, "fetch").mockResolvedValueOnce(jsonResponse({detail: "Authentication required."}, 401));

        render(<App/>);

        expect(await screen.findByRole("heading", {name: /local-first review for your strava history/i})).toBeInTheDocument();
        expect(screen.getByRole("button", {name: /continue with strava/i})).toBeInTheDocument();
    });

    it("renders dashboard data and activity detail from the backend payloads", async () => {
        vi.spyOn(global, "fetch").mockImplementation((input) => {
            const url = String(input);
            if (url.includes("/auth/session")) {
                return Promise.resolve(jsonResponse({
                    id: 1,
                    strava_athlete_id: 99,
                    display_name: "Test Athlete",
                    profile_picture_url: null
                }));
            }
            if (url.includes("/sync/status")) {
                return Promise.resolve(
                    jsonResponse({
                        status: "completed",
                        sync_type: "full_import",
                        progress_total: 10,
                        progress_completed: 10,
                        started_at: null,
                        finished_at: null,
                        error_message: null,
                    }),
                );
            }
            if (url.includes("/dashboard")) {
                return Promise.resolve(
                    jsonResponse({
                        month: [
                            {
                                current: {
                                    sport_type: "Run",
                                    period_type: "month",
                                    period_start: "2026-03-01",
                                    activity_count: 3,
                                    total_distance_meters: 42000,
                                    total_moving_time_seconds: 12600,
                                    average_pace_seconds_per_km: 300,
                                },
                                previous: {
                                    sport_type: "Run",
                                    period_type: "month",
                                    period_start: "2026-02-01",
                                    activity_count: 2,
                                    total_distance_meters: 30000,
                                    total_moving_time_seconds: 9600,
                                    average_pace_seconds_per_km: 320,
                                },
                            },
                        ],
                        year: [],
                    }),
                );
            }
            if (url.includes("/activities/11")) {
                return Promise.resolve(
                    jsonResponse({
                        id: 11,
                        sport_type: "Run",
                        name: "Morning Run",
                        description: null,
                        start_date_local: "2026-03-05T08:30:00",
                        kpis: {
                            distance_km: 10,
                            moving_time_display: "50:00",
                            summary_metric_display: "5:00 min/km",
                            total_elevation_gain_meters: 120,
                            average_heartrate_bpm: 150,
                            heart_rate_drift_bpm: 6.5,
                        },
                        map: {polyline: [[50.1, 14.4], [50.11, 14.42], [50.12, 14.43]]},
                        series: {
                            distance_km: [0, 5, 10],
                            altitude_meters: [220, 260, 240],
                            moving_average_heartrate: [140, 150, 155],
                            moving_average_speed_kph: [11, 12, 12],
                            pace_minutes_per_km: [5.2, 5.0, 4.9],
                            pace_display: ["5:12", "5:00", "4:54"],
                            slope_percent: [0.5, 1.2, -0.3],
                        },
                        thresholds: {
                            aet_heart_rate_bpm: 145,
                            ant_heart_rate_bpm: 168,
                            aet_pace_min_per_km: 5.4,
                            ant_pace_min_per_km: 4.3,
                        },
                        running_analysis: {
                            pace_distribution: [
                                {code: "below_aet", label: "Below AeT", distance_km: 2.5, share_percent: 25},
                                {code: "between_aet_ant", label: "AeT to AnT", distance_km: 6.0, share_percent: 60},
                                {code: "above_ant", label: "Above AnT", distance_km: 1.5, share_percent: 15},
                            ],
                            heart_rate_distribution: [
                                {code: "below_aet", label: "Below AeT", distance_km: 1.5, share_percent: 15},
                                {code: "between_aet_ant", label: "AeT to AnT", distance_km: 7.0, share_percent: 70},
                                {code: "above_ant", label: "Above AnT", distance_km: 1.5, share_percent: 15},
                            ],
                            agreement: {
                                matching_distance_km: 8.0,
                                matching_share_percent: 80,
                                pace_higher_distance_km: 1.0,
                                pace_higher_share_percent: 10,
                                heart_rate_higher_distance_km: 1.0,
                                heart_rate_higher_share_percent: 10,
                            },
                            steady_threshold_block: {start_distance_km: 2, end_distance_km: 7, distance_km: 5},
                            above_threshold_block: {start_distance_km: 8.5, end_distance_km: 10, distance_km: 1.5},
                            interpretation: "Pace and heart rate aligned well, with most work sitting at aet to ant.",
                            activity_evaluation: "This looked like a controlled steady run with most of the work staying in the AeT to AnT range.",
                            further_training_suggestion: "A similar threshold session is reasonable next time if recovery stays good; otherwise use an easy aerobic day.",
                        },
                    }),
                );
            }
            if (url.includes("/activities")) {
                return Promise.resolve(
                    jsonResponse({
                        items: [
                            {
                                id: 11,
                                sport_type: "Run",
                                name: "Morning Run",
                                start_date_local: "2026-03-05T08:30:00",
                                distance_km: 10,
                                moving_time_display: "50:00",
                                summary_metric_display: "5:00 /km",
                                total_elevation_gain_meters: 120,
                                average_heartrate_bpm: 150,
                                heart_rate_drift_bpm: 6.5,
                            },
                        ],
                    }),
                );
            }
            if (url.includes("/best-efforts")) {
                return Promise.resolve(
                    jsonResponse({
                        items: [{
                            sport_type: "Run",
                            effort_code: "half_marathon",
                            best_time_seconds: 5400,
                            distance_meters: 21097.5,
                            activity_id: 11,
                            achieved_at: "2026-03-05T08:30:00"
                        }],
                    }),
                );
            }
            if (url.includes("/comparisons")) {
                return Promise.resolve(
                    jsonResponse([
                        {
                            current: {
                                sport_type: "Run",
                                period_type: "month",
                                period_start: url.includes("current_period_start=2026-02-01") ? "2026-02-01" : "2026-03-01",
                                activity_count: 3,
                                total_distance_meters: 42000,
                                total_moving_time_seconds: 12600,
                                average_pace_seconds_per_km: 300,
                            },
                            previous: {
                                sport_type: "Run",
                                period_type: "month",
                                period_start: url.includes("previous_period_start=2026-01-01") ? "2026-01-01" : "2026-02-01",
                                activity_count: 2,
                                total_distance_meters: 30000,
                                total_moving_time_seconds: 9600,
                                average_pace_seconds_per_km: 320,
                            },
                        },
                    ]),
                );
            }
            if (url.includes("/trends")) {
                return Promise.resolve(
                    jsonResponse({
                        period_type: "month",
                        items: [
                            {
                                sport_type: "Run",
                                period_type: "month",
                                period_start: "2026-03-01",
                                activity_count: 3,
                                total_distance_meters: 42000,
                                total_moving_time_seconds: 12600,
                                average_pace_seconds_per_km: 300
                            },
                            {
                                sport_type: "Run",
                                period_type: "month",
                                period_start: "2026-02-01",
                                activity_count: 2,
                                total_distance_meters: 30000,
                                total_moving_time_seconds: 9600,
                                average_pace_seconds_per_km: 320
                            },
                        ],
                    }),
                );
            }
            return Promise.reject(new Error(`Unhandled fetch: ${url}`));
        });

        render(<App/>);

        expect(await screen.findByRole("heading", {name: /dashboard/i})).toBeInTheDocument();
        expect(screen.getAllByText(/^overview$/i).length).toBeGreaterThan(0);
        expect(screen.queryByText(/^selected window$/i)).not.toBeInTheDocument();
        expect((await screen.findAllByText(/03\/2026 vs 02\/2026/i)).length).toBeGreaterThan(0);

        fireEvent.click(screen.getByRole("button", {name: /activities/i}));
        fireEvent.click(screen.getByRole("button", {name: /morning run/i}));

        expect(await screen.findByRole("heading", {name: /morning run/i})).toBeInTheDocument();
        expect(screen.getByText(/^distance$/i)).toBeInTheDocument();
        expect(screen.getByText(/^moving time$/i)).toBeInTheDocument();
        expect(screen.getByText(/^hr drift$/i)).toBeInTheDocument();
        expect(screen.getAllByText("+6.5 bpm").length).toBeGreaterThan(0);
        expect(screen.getAllByText(/^pace$/i).length).toBeGreaterThan(0);
        expect(screen.getByText(/^elevation$/i)).toBeInTheDocument();
        expect(screen.getByText(/^average hr$/i)).toBeInTheDocument();
        expect(screen.queryByText(/zone summary/i)).not.toBeInTheDocument();
        expect(screen.queryByText(/intervals/i)).not.toBeInTheDocument();
        expect(screen.getByText(/running analysis/i)).toBeInTheDocument();
        expect(screen.getByText(/activity evaluation/i)).toBeInTheDocument();
        const activityEvaluationText = screen.getByText(/controlled steady run/i);
        expect(activityEvaluationText).toBeInTheDocument();
        expect(activityEvaluationText.tagName).toBe("SPAN");
        expect(screen.getByText(/further training suggestion/i)).toBeInTheDocument();
        const trainingSuggestionText = screen.getByText(/similar threshold session is reasonable next time/i);
        expect(trainingSuggestionText).toBeInTheDocument();
        expect(trainingSuggestionText.tagName).toBe("SPAN");
        expect(screen.getByText(/80%/i)).toBeInTheDocument();
        fireEvent.mouseEnter(screen.getByRole("button", {name: /pace bands explanation/i}));
        expect(await screen.findByText(/shows how your running pace was distributed/i)).toBeInTheDocument();
        expect(screen.getByLabelText("min/km chart")).toBeInTheDocument();
        expect(screen.getByLabelText("bpm chart")).toBeInTheDocument();
        expect(screen.getByLabelText("% chart")).toBeInTheDocument();

        await waitFor(() => {
            expect(global.fetch).toHaveBeenCalledWith(
                expect.stringContaining("/activities/11"),
                expect.objectContaining({credentials: "include"}),
            );
        });
    });

    it("renders the dashboard trend panel as a graph for non-rolling windows", async () => {
        vi.spyOn(global, "fetch").mockImplementation((input) => {
            const url = String(input);
            if (url.includes("/auth/session")) {
                return Promise.resolve(
                    jsonResponse({
                        id: 1,
                        strava_athlete_id: 99,
                        display_name: "Test Athlete",
                        profile_picture_url: null,
                    }),
                );
            }
            if (url.includes("/sync/status")) {
                return Promise.resolve(
                    jsonResponse({
                        status: "completed",
                        sync_type: "full_import",
                        progress_total: 10,
                        progress_completed: 10,
                    }),
                );
            }
            if (url.includes("/dashboard")) {
                return Promise.resolve(jsonResponse({month: [], year: []}));
            }
            if (url.includes("/activities")) {
                return Promise.resolve(jsonResponse({items: []}));
            }
            if (url.includes("/best-efforts")) {
                return Promise.resolve(jsonResponse({items: []}));
            }
            if (url.includes("/comparisons")) {
                return Promise.resolve(jsonResponse([]));
            }
            if (url.includes("/trends")) {
                return Promise.resolve(
                    jsonResponse({
                        period_type: "month",
                        items: [
                            {
                                sport_type: "Run",
                                period_type: "month",
                                period_start: "2026-01-01",
                                activity_count: 2,
                                total_distance_meters: 25000,
                                total_moving_time_seconds: 7200,
                                average_heart_rate_drift_bpm: 2.5,
                            },
                            {
                                sport_type: "Run",
                                period_type: "month",
                                period_start: "2026-02-01",
                                activity_count: 4,
                                total_distance_meters: 41000,
                                total_moving_time_seconds: 12600,
                                average_heart_rate_drift_bpm: 4.25,
                            },
                            {
                                sport_type: "Run",
                                period_type: "month",
                                period_start: "2026-03-01",
                                activity_count: 3,
                                total_distance_meters: 33000,
                                total_moving_time_seconds: 9900,
                                average_heart_rate_drift_bpm: 3.1,
                            },
                        ],
                    }),
                );
            }
            return Promise.reject(new Error(`Unhandled fetch: ${url}`));
        });

        render(<App/>);

        const graph = await screen.findByLabelText(/trend graph/i);
        expect(graph).toBeInTheDocument();
        expect(screen.getByText(/^km$/i)).toBeInTheDocument();
        expect(screen.getByText(/^sessions$/i)).toBeInTheDocument();
        expect(screen.getByText(/^hr drift$/i)).toBeInTheDocument();
    });

    it("lets the user choose which two monthly periods to compare", async () => {
        vi.spyOn(global, "fetch").mockImplementation((input) => {
            const url = String(input);
            if (url.includes("/auth/session")) {
                return Promise.resolve(jsonResponse({
                    id: 1,
                    strava_athlete_id: 99,
                    display_name: "Test Athlete",
                    profile_picture_url: null
                }));
            }
            if (url.includes("/sync/status")) {
                return Promise.resolve(jsonResponse({
                    status: "completed",
                    sync_type: "full_import",
                    progress_total: 10,
                    progress_completed: 10
                }));
            }
            if (url.includes("/dashboard")) {
                return Promise.resolve(jsonResponse({month: [], year: []}));
            }
            if (url.includes("/activities")) {
                return Promise.resolve(jsonResponse({items: []}));
            }
            if (url.includes("/best-efforts")) {
                return Promise.resolve(jsonResponse({items: []}));
            }
            if (url.includes("/trends")) {
                return Promise.resolve(
                    jsonResponse({
                        period_type: "month",
                        items: [
                            {
                                sport_type: "Run",
                                period_type: "month",
                                period_start: "2026-01-01",
                                activity_count: 2,
                                total_distance_meters: 25000,
                                total_moving_time_seconds: 7200
                            },
                            {
                                sport_type: "Run",
                                period_type: "month",
                                period_start: "2026-02-01",
                                activity_count: 4,
                                total_distance_meters: 41000,
                                total_moving_time_seconds: 12600
                            },
                            {
                                sport_type: "Run",
                                period_type: "month",
                                period_start: "2026-03-01",
                                activity_count: 3,
                                total_distance_meters: 33000,
                                total_moving_time_seconds: 9900
                            },
                        ],
                    }),
                );
            }
            if (url.includes("/comparisons")) {
                return Promise.resolve(jsonResponse([]));
            }
            return Promise.reject(new Error(`Unhandled fetch: ${url}`));
        });

        render(<App/>);

        expect(await screen.findByDisplayValue("03/2026")).toBeInTheDocument();
        expect(screen.getByDisplayValue("02/2026")).toBeInTheDocument();

        fireEvent.change(screen.getByLabelText(/current/i), {target: {value: "2026-02-01"}});
        fireEvent.change(screen.getByLabelText(/previous/i), {target: {value: "2026-01-01"}});

        await waitFor(() => {
            expect(global.fetch).toHaveBeenCalledWith(
                expect.stringContaining("/comparisons?period_type=month&current_period_start=2026-02-01&previous_period_start=2026-01-01"),
                expect.objectContaining({credentials: "include"}),
            );
        });
    });

    it("opens the linked activity when a best effort card is clicked", async () => {
        vi.spyOn(global, "fetch")
            .mockResolvedValueOnce(
                jsonResponse({
                    id: 1,
                    strava_athlete_id: 99,
                    display_name: "Test Athlete",
                    profile_picture_url: null,
                }),
            )
            .mockResolvedValueOnce(
                jsonResponse({
                    status: "completed",
                    sync_type: "full_import",
                    progress_total: 10,
                    progress_completed: 10,
                }),
            )
            .mockResolvedValueOnce(jsonResponse({month: [], year: []}))
            .mockResolvedValueOnce(
                jsonResponse({
                    items: [
                        {
                            id: 11,
                            sport_type: "Run",
                            name: "Morning Run",
                            start_date_local: "2026-03-05T08:30:00",
                            distance_km: 10,
                            summary_metric_display: "5:00 /km",
                        },
                    ],
                }),
            )
            .mockResolvedValueOnce(
                jsonResponse({
                    items: [
                        {
                            sport_type: "Run",
                            effort_code: "half_marathon",
                            best_time_seconds: 5400,
                            distance_meters: 21097.5,
                            activity_id: 11,
                            achieved_at: "2026-03-05T08:30:00",
                        },
                    ],
                }),
            )
            .mockResolvedValueOnce(jsonResponse([]))
            .mockResolvedValueOnce(jsonResponse({period_type: "month", items: []}))
            .mockResolvedValueOnce(
                jsonResponse({
                    id: 11,
                    sport_type: "Run",
                    name: "Morning Run",
                    description: null,
                    start_date_local: "2026-03-05T08:30:00",
                    kpis: {
                        distance_km: 10,
                        moving_time_display: "50:00",
                        summary_metric_display: "5:00 min/km",
                        total_elevation_gain_meters: 120,
                        average_heartrate_bpm: 150,
                    },
                    map: {polyline: [[50.1, 14.4], [50.11, 14.42]]},
                    series: {
                        distance_km: [0, 5, 10],
                        altitude_meters: [220, 260, 240],
                        moving_average_heartrate: [140, 150, 155],
                        moving_average_speed_kph: [11, 12, 12],
                        pace_minutes_per_km: [5.2, 5.0, 4.9],
                        pace_display: ["5:12", "5:00", "4:54"],
                        slope_percent: [0.5, 1.2, -0.3],
                    },
                    thresholds: null,
                    running_analysis: null,
                }),
            );

        render(<App/>);

        fireEvent.click(await screen.findByRole("button", {name: /best efforts/i}));
        fireEvent.click(await screen.findByRole("button", {name: /half marathon/i}));

        expect(await screen.findByRole("heading", {name: /morning run/i})).toBeInTheDocument();
    });

    it("renders cycling analysis for ride activity details", async () => {
        vi.spyOn(global, "fetch").mockImplementation((input) => {
            const url = String(input);
            if (url.includes("/auth/session")) {
                return Promise.resolve(jsonResponse({
                    id: 1,
                    strava_athlete_id: 99,
                    display_name: "Test Athlete",
                    profile_picture_url: null,
                }));
            }
            if (url.includes("/sync/status")) {
                return Promise.resolve(jsonResponse({
                    status: "completed",
                    sync_type: "full_import",
                    progress_total: 10,
                    progress_completed: 10,
                }));
            }
            if (url.includes("/dashboard")) {
                return Promise.resolve(jsonResponse({month: [], year: []}));
            }
            if (url.includes("/activities/21")) {
                return Promise.resolve(jsonResponse({
                    id: 21,
                    sport_type: "Ride",
                    name: "Morning Ride",
                    description: null,
                    start_date_local: "2026-03-05T08:30:00",
                    kpis: {
                        distance_km: 42,
                        moving_time_display: "1:45:00",
                        summary_metric_display: "24.0 km/h",
                        summary_metric_kind: "speed",
                        total_elevation_gain_meters: 520,
                        average_heartrate_bpm: 148,
                        average_cadence: 88,
                        heart_rate_drift_bpm: 4.2,
                    },
                    map: {polyline: [[50.1, 14.4], [50.11, 14.42], [50.12, 14.43]]},
                    series: {
                        distance_km: [0, 20, 42],
                        altitude_meters: [220, 410, 260],
                        moving_average_heartrate: [136, 149, 168],
                        moving_average_speed_kph: [22, 24, 31],
                        pace_minutes_per_km: [],
                        pace_display: [],
                        slope_percent: [0.5, 3.2, -2.1],
                    },
                    thresholds: {
                        aet_heart_rate_bpm: 145,
                        ant_heart_rate_bpm: 168,
                        aet_pace_min_per_km: null,
                        ant_pace_min_per_km: null,
                    },
                    running_analysis: null,
                    cycling_analysis: {
                        speed_distribution: [
                            {code: "below_steady", label: "Below Steady", distance_km: 10, share_percent: 24},
                            {code: "steady_speed", label: "Steady Speed", distance_km: 24, share_percent: 57},
                            {code: "above_steady", label: "Above Steady", distance_km: 8, share_percent: 19},
                        ],
                        heart_rate_distribution: [
                            {code: "below_aet", label: "Below AeT", distance_km: 14, share_percent: 33},
                            {code: "between_aet_ant", label: "AeT to AnT", distance_km: 22, share_percent: 52},
                            {code: "above_ant", label: "Above AnT", distance_km: 6, share_percent: 15},
                        ],
                        climbing_summary: {
                            climbing_distance_km: 16,
                            climbing_share_percent: 38,
                            flat_distance_km: 18,
                            flat_share_percent: 43,
                            descending_distance_km: 8,
                            descending_share_percent: 19,
                        },
                        steady_aerobic_block: {start_distance_km: 0, end_distance_km: 12, distance_km: 12},
                        above_threshold_block: {start_distance_km: 31, end_distance_km: 36, distance_km: 5},
                        average_cadence: 88,
                        activity_evaluation: "This looked like a hilly ride with meaningful high-cardiac-load segments on the climbs.",
                        further_training_suggestion: "Follow this with an easier spin or recovery day so the harder cardiovascular load has room to absorb.",
                    },
                }));
            }
            if (url.includes("/activities")) {
                return Promise.resolve(jsonResponse({
                    items: [
                        {
                            id: 21,
                            sport_type: "Ride",
                            name: "Morning Ride",
                            start_date_local: "2026-03-05T08:30:00",
                            distance_km: 42,
                            moving_time_display: "1:45:00",
                            summary_metric_display: "24.0 km/h",
                            summary_metric_kind: "speed",
                            total_elevation_gain_meters: 520,
                            average_heartrate_bpm: 148,
                            heart_rate_drift_bpm: 4.2,
                        },
                    ],
                }));
            }
            if (url.includes("/best-efforts")) {
                return Promise.resolve(jsonResponse({items: []}));
            }
            if (url.includes("/comparisons")) {
                return Promise.resolve(jsonResponse([]));
            }
            if (url.includes("/trends")) {
                return Promise.resolve(jsonResponse({period_type: "month", items: []}));
            }
            return Promise.reject(new Error(`Unhandled fetch: ${url}`));
        });

        render(<App/>);

        fireEvent.click(await screen.findByRole("button", {name: /activities/i}));
        fireEvent.click(screen.getByRole("button", {name: /morning ride/i}));

        expect(await screen.findByRole("heading", {name: /morning ride/i})).toBeInTheDocument();
        expect(screen.getByText(/cycling analysis/i)).toBeInTheDocument();
        expect(screen.getByText(/speed bands/i)).toBeInTheDocument();
        expect(screen.getByText(/average cadence/i)).toBeInTheDocument();
        expect(screen.getAllByText(/88 rpm/i).length).toBeGreaterThan(0);
        expect(screen.getByText(/hilly ride with meaningful high-cardiac-load segments/i)).toBeInTheDocument();
        expect(screen.getByLabelText("km/h chart")).toBeInTheDocument();
    });

    it("shows cycling best efforts when the ride filter is selected", async () => {
        vi.spyOn(global, "fetch").mockImplementation((input) => {
            const url = String(input);
            if (url.includes("/auth/session")) {
                return Promise.resolve(jsonResponse({
                    id: 1,
                    strava_athlete_id: 99,
                    display_name: "Test Athlete",
                    profile_picture_url: null,
                }));
            }
            if (url.includes("/sync/status")) {
                return Promise.resolve(jsonResponse({
                    status: "completed",
                    sync_type: "full_import",
                    progress_total: 10,
                    progress_completed: 10,
                }));
            }
            if (url.includes("/dashboard")) {
                return Promise.resolve(jsonResponse({month: [], year: []}));
            }
            if (url.includes("/activities")) {
                return Promise.resolve(jsonResponse({items: []}));
            }
            if (url.includes("/best-efforts")) {
                return Promise.resolve(jsonResponse({
                    items: url.includes("sport_type=Ride")
                        ? [{
                            sport_type: "Ride",
                            effort_code: "50km",
                            best_time_seconds: 5400,
                            distance_meters: 50000,
                            activity_id: 21,
                            achieved_at: "2026-03-05T08:30:00",
                        }]
                        : [],
                }));
            }
            if (url.includes("/comparisons")) {
                return Promise.resolve(jsonResponse([]));
            }
            if (url.includes("/trends")) {
                return Promise.resolve(jsonResponse({period_type: "month", items: []}));
            }
            return Promise.reject(new Error(`Unhandled fetch: ${url}`));
        });

        render(<App/>);

        fireEvent.change(await screen.findByLabelText("Sport"), {target: {value: "Ride"}});
        fireEvent.click(await screen.findByRole("button", {name: /best efforts/i}));

        expect(await screen.findByRole("heading", {name: /cycling marks/i})).toBeInTheDocument();
        expect(screen.getAllByText(/^ride$/i).length).toBeGreaterThan(0);
        expect(screen.getByText("50 km")).toBeInTheDocument();
    });

    it("aggregates daily calendar distance into a single day bubble", async () => {
        vi.spyOn(global, "fetch")
            .mockResolvedValueOnce(
                jsonResponse({
                    id: 1,
                    strava_athlete_id: 99,
                    display_name: "Test Athlete",
                    profile_picture_url: null,
                }),
            )
            .mockResolvedValueOnce(
                jsonResponse({
                    status: "completed",
                    sync_type: "full_import",
                    progress_total: 10,
                    progress_completed: 10,
                }),
            )
            .mockResolvedValueOnce(jsonResponse({month: [], year: []}))
            .mockResolvedValueOnce(
                jsonResponse({
                    items: [
                        {
                            id: 11,
                            sport_type: "Run",
                            name: "Morning Run",
                            start_date_local: "2026-03-05T08:30:00",
                            distance_km: 10,
                            summary_metric_display: "5:00 /km",
                        },
                        {
                            id: 12,
                            sport_type: "Run",
                            name: "Evening Run",
                            start_date_local: "2026-03-05T18:30:00",
                            distance_km: 5,
                            summary_metric_display: "5:30 /km",
                        },
                    ],
                }),
            )
            .mockResolvedValueOnce(jsonResponse({items: []}))
            .mockResolvedValueOnce(jsonResponse([]))
            .mockResolvedValueOnce(jsonResponse({period_type: "month", items: []}));

        render(<App/>);

        fireEvent.click(await screen.findByRole("button", {name: /calendar/i}));

        expect(await screen.findByText(/2 activities/i)).toBeInTheDocument();
        const bubble = screen.getByRole("button", {name: /15 km/i});
        expect(bubble).toBeInTheDocument();
        expect(bubble).toHaveClass("is-run");
    });

    it("renders cycling calendar days with the cycling color class", async () => {
        vi.spyOn(global, "fetch")
            .mockResolvedValueOnce(
                jsonResponse({
                    id: 1,
                    strava_athlete_id: 99,
                    display_name: "Test Athlete",
                    profile_picture_url: null,
                }),
            )
            .mockResolvedValueOnce(
                jsonResponse({
                    status: "completed",
                    sync_type: "full_import",
                    progress_total: 10,
                    progress_completed: 10,
                }),
            )
            .mockResolvedValueOnce(jsonResponse({month: [], year: []}))
            .mockResolvedValueOnce(
                jsonResponse({
                    items: [
                        {
                            id: 21,
                            sport_type: "Ride",
                            name: "Morning Ride",
                            start_date_local: "2026-03-06T08:30:00",
                            distance_km: 42,
                            summary_metric_display: "28 km/h",
                        },
                    ],
                }),
            )
            .mockResolvedValueOnce(jsonResponse({items: []}))
            .mockResolvedValueOnce(jsonResponse([]))
            .mockResolvedValueOnce(jsonResponse({period_type: "month", items: []}));

        render(<App/>);

        fireEvent.click(await screen.findByRole("button", {name: /calendar/i}));

        const bubble = await screen.findByRole("button", {name: /42 km/i});
        expect(bubble).toHaveClass("is-ride");
    });

    it("uses run distance buckets for calendar bubble sizing", async () => {
        vi.spyOn(global, "fetch")
            .mockResolvedValueOnce(
                jsonResponse({
                    id: 1,
                    strava_athlete_id: 99,
                    display_name: "Test Athlete",
                    profile_picture_url: null,
                }),
            )
            .mockResolvedValueOnce(
                jsonResponse({
                    status: "completed",
                    sync_type: "full_import",
                    progress_total: 10,
                    progress_completed: 10,
                }),
            )
            .mockResolvedValueOnce(jsonResponse({month: [], year: []}))
            .mockResolvedValueOnce(
                jsonResponse({
                    items: [
                        {
                            id: 31,
                            sport_type: "Run",
                            name: "Easy Run",
                            start_date_local: "2026-03-03T08:30:00",
                            distance_km: 8,
                            summary_metric_display: "6:00 /km",
                        },
                        {
                            id: 32,
                            sport_type: "Run",
                            name: "Half Marathon Effort",
                            start_date_local: "2026-03-04T08:30:00",
                            distance_km: 18,
                            summary_metric_display: "5:00 /km",
                        },
                        {
                            id: 33,
                            sport_type: "Run",
                            name: "Long Run",
                            start_date_local: "2026-03-05T08:30:00",
                            distance_km: 30,
                            summary_metric_display: "5:15 /km",
                        },
                    ],
                }),
            )
            .mockResolvedValueOnce(jsonResponse({items: []}))
            .mockResolvedValueOnce(jsonResponse([]))
            .mockResolvedValueOnce(jsonResponse({period_type: "month", items: []}));

        render(<App/>);

        fireEvent.click(await screen.findByRole("button", {name: /calendar/i}));

        const shortBubble = await screen.findByRole("button", {name: /^8 km$/i});
        const mediumBubble = await screen.findByRole("button", {name: /^18 km$/i});
        const longBubble = await screen.findByRole("button", {name: /^30 km$/i});

        expect(shortBubble.style.getPropertyValue("--bubble-size")).toBe("32px");
        expect(mediumBubble.style.getPropertyValue("--bubble-size")).toBe("46px");
        expect(longBubble.style.getPropertyValue("--bubble-size")).toBe("60px");
    });

    it("uses 20 km ride buckets for calendar bubble sizing", async () => {
        vi.spyOn(global, "fetch")
            .mockResolvedValueOnce(
                jsonResponse({
                    id: 1,
                    strava_athlete_id: 99,
                    display_name: "Test Athlete",
                    profile_picture_url: null,
                }),
            )
            .mockResolvedValueOnce(
                jsonResponse({
                    status: "completed",
                    sync_type: "full_import",
                    progress_total: 10,
                    progress_completed: 10,
                }),
            )
            .mockResolvedValueOnce(jsonResponse({month: [], year: []}))
            .mockResolvedValueOnce(
                jsonResponse({
                    items: [
                        {
                            id: 41,
                            sport_type: "Ride",
                            name: "Short Ride",
                            start_date_local: "2026-03-03T08:30:00",
                            distance_km: 20,
                            summary_metric_display: "25 km/h",
                        },
                        {
                            id: 42,
                            sport_type: "Ride",
                            name: "Big Ride",
                            start_date_local: "2026-03-04T08:30:00",
                            distance_km: 100,
                            summary_metric_display: "28 km/h",
                        },
                    ],
                }),
            )
            .mockResolvedValueOnce(jsonResponse({items: []}))
            .mockResolvedValueOnce(jsonResponse([]))
            .mockResolvedValueOnce(jsonResponse({period_type: "month", items: []}));

        render(<App/>);

        fireEvent.click(await screen.findByRole("button", {name: /calendar/i}));

        const shortRideBubble = await screen.findByRole("button", {name: /^20 km$/i});
        const longRideBubble = await screen.findByRole("button", {name: /^100 km$/i});

        expect(shortRideBubble.style.getPropertyValue("--bubble-size")).toBe("33px");
        expect(longRideBubble.style.getPropertyValue("--bubble-size")).toBe("53px");
    });

    it("registers sync polling while a sync is running", async () => {
        let intervalCallback = null;
        let syncPollCount = 0;
        vi.spyOn(window, "setInterval").mockImplementation((callback) => {
            intervalCallback = callback;
            return 1;
        });
        vi.spyOn(window, "clearInterval").mockImplementation(() => {
        });
        vi.spyOn(global, "fetch").mockImplementation((input) => {
            const url = String(input);
            if (url.includes("/auth/session")) {
                return Promise.resolve(
                    jsonResponse({
                        id: 1,
                        strava_athlete_id: 99,
                        display_name: "Test Athlete",
                        profile_picture_url: null,
                    }),
                );
            }
            if (url.includes("/sync/status")) {
                syncPollCount += 1;
                return Promise.resolve(
                    jsonResponse({
                        status: "running",
                        sync_type: "incremental_sync",
                        progress_total: 10,
                        progress_completed: syncPollCount === 1 ? 1 : 2,
                    }),
                );
            }
            if (url.includes("/dashboard")) {
                return Promise.resolve(jsonResponse({month: [], year: []}));
            }
            if (url.includes("/activities")) {
                return Promise.resolve(jsonResponse({items: []}));
            }
            if (url.includes("/best-efforts")) {
                return Promise.resolve(jsonResponse({items: []}));
            }
            if (url.includes("/comparisons")) {
                return Promise.resolve(jsonResponse([]));
            }
            if (url.includes("/trends")) {
                return Promise.resolve(jsonResponse({period_type: "month", items: []}));
            }
            if (url.includes("/me/profile")) {
                return Promise.resolve(
                    jsonResponse({
                        aet_heart_rate_bpm: null,
                        ant_heart_rate_bpm: null,
                        aet_pace_min_per_km: null,
                        ant_pace_min_per_km: null,
                    }),
                );
            }
            throw new Error(`Unhandled fetch request in test: ${url}`);
        });

        render(<App/>);

        fireEvent.click(await screen.findByRole("button", {name: /settings/i}));

        expect(await screen.findByText("1 / 10")).toBeInTheDocument();
        expect(intervalCallback).not.toBeNull();
    });

    it("shows only the controls relevant to the selected view", async () => {
        vi.spyOn(global, "fetch")
            .mockResolvedValueOnce(
                jsonResponse({
                    id: 1,
                    strava_athlete_id: 99,
                    display_name: "Test Athlete",
                    profile_picture_url: null,
                }),
            )
            .mockResolvedValueOnce(
                jsonResponse({
                    status: "completed",
                    sync_type: "full_import",
                    progress_total: 10,
                    progress_completed: 10,
                }),
            )
            .mockResolvedValueOnce(jsonResponse({month: [], year: []}))
            .mockResolvedValueOnce(jsonResponse({items: []}))
            .mockResolvedValueOnce(jsonResponse({items: []}))
            .mockResolvedValueOnce(jsonResponse([]))
            .mockResolvedValueOnce(jsonResponse({period_type: "month", items: []}));

        render(<App/>);

        expect(await screen.findByRole("heading", {name: /dashboard/i})).toBeInTheDocument();
        expect(screen.getByText("Sport")).toBeInTheDocument();
        expect(screen.getByText("Window")).toBeInTheDocument();
        expect(screen.queryByText("From")).not.toBeInTheDocument();
        expect(screen.queryByText("To")).not.toBeInTheDocument();

        fireEvent.click(screen.getByRole("button", {name: /activities/i}));
        expect(await screen.findByRole("heading", {name: /activities/i})).toBeInTheDocument();
        expect(screen.getByText("Sport")).toBeInTheDocument();
        expect(screen.getByText("From")).toBeInTheDocument();
        expect(screen.getByText("To")).toBeInTheDocument();
        expect(screen.queryByText("Window")).not.toBeInTheDocument();

        fireEvent.click(screen.getByRole("button", {name: /calendar/i}));
        expect(await screen.findByRole("heading", {name: /calendar/i})).toBeInTheDocument();
        expect(screen.getByText("Sport")).toBeInTheDocument();
        expect(screen.queryByText("Window")).not.toBeInTheDocument();
        expect(screen.queryByText("From")).not.toBeInTheDocument();
        expect(screen.queryByText("To")).not.toBeInTheDocument();
    });

    it("loads and saves profile settings from the settings view", async () => {
        vi.spyOn(global, "fetch")
            .mockResolvedValueOnce(
                jsonResponse({
                    id: 1,
                    strava_athlete_id: 99,
                    display_name: "Test Athlete",
                    profile_picture_url: null,
                }),
            )
            .mockResolvedValueOnce(
                jsonResponse({
                    status: "completed",
                    sync_type: "full_import",
                    progress_total: 10,
                    progress_completed: 10,
                }),
            )
            .mockResolvedValueOnce(jsonResponse({month: [], year: []}))
            .mockResolvedValueOnce(jsonResponse({items: []}))
            .mockResolvedValueOnce(jsonResponse({items: []}))
            .mockResolvedValueOnce(jsonResponse([]))
            .mockResolvedValueOnce(jsonResponse({period_type: "month", items: []}))
            .mockResolvedValueOnce(
                jsonResponse({
                    aet_heart_rate_bpm: 145,
                    ant_heart_rate_bpm: 168,
                    aet_pace_min_per_km: "5.40",
                    ant_pace_min_per_km: "4.30",
                }),
            )
            .mockResolvedValueOnce(
                jsonResponse({
                    aet_heart_rate_bpm: 148,
                    ant_heart_rate_bpm: 170,
                    aet_pace_min_per_km: "5.20",
                    ant_pace_min_per_km: "4.10",
                }),
            );

        render(<App/>);

        fireEvent.click(await screen.findByRole("button", {name: /settings/i}));

        const aerobicPaceInput = await screen.findByLabelText("Aerobic Threshold Pace (min/km)");
        expect(screen.getByRole("button", {name: /refresh sync/i})).toBeInTheDocument();
        expect(screen.queryByText(/latest sync/i)).not.toBeInTheDocument();
        expect(screen.getByLabelText("Aerobic Threshold HR (bpm)")).toHaveValue(145);
        expect(screen.getByLabelText("Aerobic Threshold Pace (min/km)")).toHaveValue("5:24");
        expect(screen.queryByText(/session model/i)).not.toBeInTheDocument();
        expect(screen.queryByText(/profile image/i)).not.toBeInTheDocument();
        fireEvent.change(aerobicPaceInput, {target: {value: "5:20"}});
        fireEvent.change(screen.getByLabelText("Aerobic Threshold HR (bpm)"), {target: {value: "148"}});
        fireEvent.change(screen.getByLabelText("Anaerobic Threshold HR (bpm)"), {target: {value: "170"}});
        fireEvent.change(screen.getByLabelText("Anaerobic Threshold Pace (min/km)"), {target: {value: "4:10"}});
        fireEvent.click(screen.getByRole("button", {name: /save profile/i}));

        await waitFor(() => {
            expect(global.fetch).toHaveBeenCalledWith(
                expect.stringContaining("/me/profile"),
                expect.objectContaining({
                    body: JSON.stringify({
                        aet_heart_rate_bpm: 148,
                        ant_heart_rate_bpm: 170,
                        aet_pace_min_per_km: 5.33,
                        ant_pace_min_per_km: 4.17,
                    }),
                    method: "PUT",
                }),
            );
        });
    });
});

describe("activity detail chart baselines", () => {
    it("parses average pace and speed summary metrics", () => {
        expect(parseSummaryMetricAverage("5:00 min/km", "pace")).toBe(5);
        expect(parseSummaryMetricAverage("28 km/h", "speed")).toBe(28);
    });

    it("falls back to series averages and keeps slope pinned to zero", () => {
        expect(resolveDetailReferenceValue({valueKind: "slope", values: [2, 4, -1]})).toBe(0);
        expect(
            resolveDetailReferenceValue({
                averageValue: null,
                valueKind: "heart_rate",
                values: [140, 150, 160],
            }),
        ).toBe(150);
        expect(
            resolveDetailReferenceValue({
                averageValue: "5:00 min/km",
                summaryMetricKind: "pace",
                valueKind: "pace",
                values: [5.2, 5.0, 4.9],
            }),
        ).toBe(5);
    });

    it("builds threshold bands for pace and heart rate while preserving pace axis semantics", () => {
        const thresholds = {
            aet_heart_rate_bpm: 145,
            ant_heart_rate_bpm: 168,
            aet_pace_min_per_km: 5.4,
            ant_pace_min_per_km: 4.3,
        };

        const paceGuides = buildThresholdGuides({
            maxValue: 6.2,
            minValue: 4.0,
            thresholds,
            valueKind: "pace",
            xMax: 10,
            xMin: 0,
        });
        expect(paceGuides.lines.map((line) => line.label)).toEqual(["AeT", "AnT"]);
        expect(paceGuides.bands.map((band) => band.code)).toEqual(["above_ant", "between_aet_ant", "below_aet"]);
        expect(paceGuides.bands[0].y1).toBe(4.0);
        expect(paceGuides.bands[0].y2).toBe(4.3);
        expect(paceGuides.bands[2].y1).toBe(5.4);
        expect(paceGuides.bands[2].y2).toBe(6.2);

        const heartRateGuides = buildThresholdGuides({
            maxValue: 180,
            minValue: 130,
            thresholds,
            valueKind: "heart_rate",
            xMax: 10,
            xMin: 0,
        });
        expect(heartRateGuides.bands.map((band) => band.code)).toEqual(["below_aet", "between_aet_ant", "above_ant"]);
        expect(heartRateGuides.bands[0].y1).toBe(130);
        expect(heartRateGuides.bands[0].y2).toBe(145);
        expect(heartRateGuides.bands[2].y1).toBe(168);
        expect(heartRateGuides.bands[2].y2).toBe(180);
    });
});
