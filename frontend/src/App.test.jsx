import {act, fireEvent, render, screen, waitFor, within} from "@testing-library/react";

import App from "./App";
import {buildThresholdGuides, buildCalendarSummary, parseSummaryMetricAverage, resolveDetailReferenceValue} from "./utils/data";
import {formatAltitudeAxisValue, formatAxisValue} from "./utils/formatters";

function jsonResponse(body, status = 200) {
    return {
        ok: status >= 200 && status < 300,
        status,
        headers: {
            get: vi.fn().mockReturnValue("application/json"),
        },
        json: vi.fn().mockResolvedValue(body),
    };
}

describe("App", () => {
    afterEach(() => {
        vi.restoreAllMocks();
        vi.unstubAllGlobals();
    });

    it("renders the login screen when the session is anonymous", async () => {
        vi.spyOn(global, "fetch").mockImplementation((input) => {
            const url = String(input);
            if (url.includes("/auth/session")) {
                return Promise.resolve(jsonResponse({detail: "Authentication required."}, 401));
            }
            if (url.includes("/auth/strava/credentials")) {
                return Promise.resolve(jsonResponse({
                    client_id: null,
                    has_saved_secret: false,
                    can_connect: false,
                    strava_api_settings_url: "https://www.strava.com/settings/api",
                }));
            }
            return Promise.reject(new Error(`Unhandled fetch: ${url}`));
        });

        render(<App/>);

        expect(await screen.findByRole("heading", {name: /your strava history, kept simple/i})).toBeInTheDocument();
        expect(screen.getByRole("button", {name: /login to strava/i})).toBeInTheDocument();
        expect(screen.getByText(/login once\. review everything locally\./i)).toBeInTheDocument();
        expect(screen.getByText(/^strava$/i)).toBeInTheDocument();
        expect(screen.getByRole("button", {name: /set strava credentials/i})).toBeInTheDocument();
        expect(screen.queryByText(/setup required/i)).not.toBeInTheDocument();
        expect(screen.queryByText(/flow/i)).not.toBeInTheDocument();
        expect(screen.queryByText(/strava api settings/i)).not.toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", {name: /login to strava/i}));
        expect(await screen.findByRole("dialog", {name: /set up your strava app/i})).toBeInTheDocument();
        expect(screen.queryByText(/strava api settings/i)).not.toBeInTheDocument();
    });

    it("renders the shared auth screen with saved credentials after logout", async () => {
        vi.spyOn(global, "fetch").mockImplementation((input, init) => {
            const url = String(input);
            if (url.includes("/auth/session")) {
                return Promise.resolve(jsonResponse({
                    id: 1,
                    strava_athlete_id: 99,
                    display_name: "Test Athlete",
                    profile_picture_url: null,
                }));
            }
            if (url.includes("/auth/logout")) {
                expect(init?.method).toBe("POST");
                return Promise.resolve({ok: true, status: 204, headers: {get: vi.fn().mockReturnValue(null)}});
            }
            if (url.includes("/auth/strava/credentials")) {
                return Promise.resolve(jsonResponse({
                    client_id: "12345",
                    has_saved_secret: true,
                    can_connect: true,
                    strava_api_settings_url: "https://www.strava.com/settings/api",
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
                return Promise.resolve(jsonResponse({items: [], current: null}));
            }
            return Promise.reject(new Error(`Unhandled fetch: ${url}`));
        });

        render(<App/>);

        expect(await screen.findByRole("heading", {name: /dashboard/i})).toBeInTheDocument();

        fireEvent.click(screen.getByRole("button", {name: /settings/i}));
        fireEvent.click(await screen.findByRole("button", {name: /log out/i}));

        expect(await screen.findByRole("heading", {name: /back to your training archive\./i})).toBeInTheDocument();
        expect(screen.getByRole("button", {name: /login to strava/i})).toBeInTheDocument();
        expect(screen.getByText(/^strava$/i)).toBeInTheDocument();
        expect(screen.getByText(/ready when you are\./i)).toBeInTheDocument();
        expect(screen.getByRole("button", {name: /set strava credentials/i})).toBeInTheDocument();
        expect(screen.getByText(/compatible with strava/i)).toBeInTheDocument();
        expect(screen.getByText(/not developed or sponsored by strava/i)).toBeInTheDocument();
    });

    it("stages manual credentials in the setup modal and uses them for login", async () => {
        const assignSpy = vi.fn();
        vi.stubGlobal("location", {...window.location, assign: assignSpy});
        vi.spyOn(global, "fetch").mockImplementation((input, init) => {
            const url = String(input);
            if (url.includes("/auth/session")) {
                return Promise.resolve(jsonResponse({detail: "Authentication required."}, 401));
            }
            if (url.includes("/auth/strava/credentials")) {
                return Promise.resolve(jsonResponse({
                    client_id: null,
                    has_saved_secret: false,
                    can_connect: false,
                    strava_api_settings_url: "https://www.strava.com/settings/api",
                }));
            }
            if (url.includes("/auth/strava/login")) {
                expect(init?.method).toBe("POST");
                expect(init?.body).toBe(JSON.stringify({
                    client_id: "45678",
                    client_secret: "super-secret",
                    use_saved_credentials: false,
                }));
                return Promise.resolve(jsonResponse({authorization_url: "https://www.strava.com/oauth/authorize"}));
            }
            return Promise.reject(new Error(`Unhandled fetch: ${url}`));
        });

        render(<App/>);

        fireEvent.click(await screen.findByRole("button", {name: /set strava credentials/i}));
        fireEvent.change(screen.getByLabelText("Strava Client ID"), {target: {value: "45678"}});
        fireEvent.change(screen.getByLabelText("Strava Client Secret"), {target: {value: "super-secret"}});
        fireEvent.click(screen.getByRole("button", {name: /save for next login/i}));

        expect(screen.queryByRole("dialog", {name: /set up your strava app/i})).not.toBeInTheDocument();
        expect(screen.getByText(/ready for login\./i)).toBeInTheDocument();

        fireEvent.click(screen.getByRole("button", {name: /login to strava/i}));

        await waitFor(() => {
            expect(global.fetch).toHaveBeenCalledWith(
                expect.stringContaining("/auth/strava/login"),
                expect.objectContaining({
                    body: JSON.stringify({
                        client_id: "45678",
                        client_secret: "super-secret",
                        use_saved_credentials: false,
                    }),
                    method: "POST",
                }),
            );
        });
        expect(assignSpy).toHaveBeenCalledWith("https://www.strava.com/oauth/authorize");
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
        expect(within(screen.getByLabelText("min/km chart")).getByText("Distance: 0 km")).toBeInTheDocument();
        expect(within(screen.getByLabelText("min/km chart")).getByText("Pace: 5:12 /km")).toBeInTheDocument();
        expect(within(screen.getByLabelText("bpm chart")).getByText("Heart Rate: 140 bpm")).toBeInTheDocument();
        expect(within(screen.getByLabelText("% chart")).getByText("Slope: 0.5%")).toBeInTheDocument();

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

    it("hides the broken 30 day window and labels weekly comparison selectors by week within the month", async () => {
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
            if (url.includes("/trends?period_type=week")) {
                return Promise.resolve(
                    jsonResponse({
                        period_type: "week",
                        items: [
                            {sport_type: "Run", period_type: "week", period_start: "2026-03-02", activity_count: 1, total_distance_meters: 10000, total_moving_time_seconds: 3000},
                            {sport_type: "Run", period_type: "week", period_start: "2026-03-09", activity_count: 2, total_distance_meters: 15000, total_moving_time_seconds: 4500},
                            {sport_type: "Run", period_type: "week", period_start: "2026-03-16", activity_count: 3, total_distance_meters: 20000, total_moving_time_seconds: 6000},
                            {sport_type: "Run", period_type: "week", period_start: "2026-03-23", activity_count: 4, total_distance_meters: 25000, total_moving_time_seconds: 7500},
                        ],
                    }),
                );
            }
            if (url.includes("/trends")) {
                return Promise.resolve(jsonResponse({period_type: "month", items: []}));
            }
            if (url.includes("/comparisons")) {
                return Promise.resolve(jsonResponse([]));
            }
            return Promise.reject(new Error(`Unhandled fetch: ${url}`));
        });

        render(<App/>);

        expect(await screen.findByLabelText(/window/i)).toBeInTheDocument();
        expect(screen.queryByRole("option", {name: /30 days/i})).not.toBeInTheDocument();

        fireEvent.change(screen.getByLabelText(/window/i), {target: {value: "week"}});

        expect(await screen.findByDisplayValue("W4 Mar 2026")).toBeInTheDocument();
        expect(screen.getByDisplayValue("W3 Mar 2026")).toBeInTheDocument();
        expect(screen.getAllByRole("option", {name: "W1 Mar 2026"}).length).toBeGreaterThan(0);
        expect(screen.getAllByRole("option", {name: "W2 Mar 2026"}).length).toBeGreaterThan(0);
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
        fireEvent.click(await screen.findByRole("button", {name: /morning ride/i}));

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

    it("renders activity list rows with name and distance on top and date plus type aligned below", async () => {
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
                            id: 51,
                            sport_type: "Run",
                            name: "Morning Session",
                            start_date_local: "2026-03-05T08:30:00",
                            distance_km: 18,
                            moving_time_display: "1:30:00",
                            summary_metric_display: "5:00 /km",
                            total_elevation_gain_meters: 120,
                            average_heartrate_bpm: 150,
                            heart_rate_drift_bpm: 2.5,
                        },
                    ],
                }),
            )
            .mockResolvedValueOnce(jsonResponse({items: []}))
            .mockResolvedValueOnce(jsonResponse([]))
            .mockResolvedValueOnce(jsonResponse({period_type: "month", items: []}));

        render(<App/>);

        fireEvent.click(await screen.findByRole("button", {name: /activities/i}));

        const name = await screen.findByText("Morning Session");
        const row = name.closest("button");
        expect(row).not.toBeNull();
        expect(row).toHaveTextContent("Mar 5, 2026");
        expect(row).toHaveTextContent("18 km");
        expect(row).toHaveTextContent("Run");
        expect(row.querySelector(".activity-row-left")).not.toBeNull();
        expect(row.querySelector(".activity-row-right")).not.toBeNull();
        expect(row.querySelector(".activity-row-name")).toHaveTextContent("Morning Session");
        expect(row.querySelector(".activity-row-date")).toHaveTextContent("Mar 5, 2026");
        expect(row.querySelector(".activity-row-distance")).toHaveTextContent("18 km");
        expect(row.querySelector(".activity-row-type")).toHaveTextContent("Run");
        expect(row.querySelector(".activity-row-bubble")).toBeNull();
    });

    it("renders e-bike activity rows with the activity type on the same metadata line as the date", async () => {
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
                            id: 52,
                            sport_type: "EBikeRide",
                            name: "Hill Commute",
                            start_date_local: "2026-03-06T07:15:00",
                            distance_km: 100,
                            moving_time_display: "3:20:00",
                            summary_metric_display: "30 km/h",
                            total_elevation_gain_meters: 500,
                            average_heartrate_bpm: 135,
                            heart_rate_drift_bpm: 1.4,
                        },
                    ],
                }),
            )
            .mockResolvedValueOnce(jsonResponse({items: []}))
            .mockResolvedValueOnce(jsonResponse([]))
            .mockResolvedValueOnce(jsonResponse({period_type: "month", items: []}));

        render(<App/>);

        fireEvent.click(await screen.findByRole("button", {name: /activities/i}));

        const row = (await screen.findByText("Hill Commute")).closest("button");
        expect(row).not.toBeNull();
        expect(row).toHaveTextContent("100 km");
        expect(row).toHaveTextContent("E-Bike");
        expect(row.querySelector(".activity-row-date")).toHaveTextContent("Mar 6, 2026");
        expect(row.querySelector(".activity-row-type")).toHaveTextContent("E-Bike");
        expect(row.querySelector(".activity-row-bubble")).toBeNull();
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

        expect(shortBubble.style.getPropertyValue("--bubble-size")).toBe("22px");
        expect(mediumBubble.style.getPropertyValue("--bubble-size")).toBe("32px");
        expect(longBubble.style.getPropertyValue("--bubble-size")).toBe("42px");
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

        expect(shortRideBubble.style.getPropertyValue("--bubble-size")).toBe("23px");
        expect(longRideBubble.style.getPropertyValue("--bubble-size")).toBe("39px");
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
                        items: [],
                        current: null,
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
        expect(screen.getByText("Month")).toBeInTheDocument();
        expect(screen.queryByText("Window")).not.toBeInTheDocument();
        expect(screen.queryByText("From")).not.toBeInTheDocument();
        expect(screen.queryByText("To")).not.toBeInTheDocument();
    });

    it("lets the user jump directly to a month from the calendar toolbar", async () => {
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
                            id: 51,
                            sport_type: "Run",
                            name: "March Run",
                            start_date_local: "2026-03-05T08:30:00",
                            distance_km: 10,
                            summary_metric_display: "5:20 /km",
                        },
                        {
                            id: 52,
                            sport_type: "Run",
                            name: "February Run",
                            start_date_local: "2026-02-10T08:30:00",
                            distance_km: 12,
                            summary_metric_display: "5:10 /km",
                        },
                    ],
                }),
            )
            .mockResolvedValueOnce(jsonResponse({items: []}))
            .mockResolvedValueOnce(jsonResponse([]))
            .mockResolvedValueOnce(jsonResponse({period_type: "month", items: []}));

        render(<App/>);

        fireEvent.click(await screen.findByRole("button", {name: /calendar/i}));

        expect(await screen.findByText(/march 2026/i)).toBeInTheDocument();
        expect(screen.getByRole("button", {name: /^10 km$/i})).toBeInTheDocument();

        fireEvent.change(screen.getByLabelText("Month"), {target: {value: "2026-02"}});

        expect(await screen.findByText(/february 2026/i)).toBeInTheDocument();
        expect(screen.getByRole("button", {name: /^12 km$/i})).toBeInTheDocument();
    });

    it("shows the admin page only for the admin athlete and lets them reject a user", async () => {
        vi.spyOn(global, "fetch").mockImplementation((input, init) => {
            const url = String(input);
            if (url.includes("/auth/session")) {
                return Promise.resolve(jsonResponse({
                    id: 1,
                    strava_athlete_id: 102168741,
                    display_name: "Admin Athlete",
                    profile_picture_url: null,
                }));
            }
            if (url.includes("/sync/status")) {
                return Promise.resolve(jsonResponse({status: "idle"}));
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
            if (url.includes("/admin/users") && !init?.method) {
                return Promise.resolve(jsonResponse({
                    items: [
                        {
                            id: 1,
                            strava_athlete_id: 102168741,
                            display_name: "Admin Athlete",
                            email: null,
                            is_active: true,
                            created_at: "2026-03-20T09:00:00Z",
                            updated_at: "2026-03-23T09:00:00Z",
                            last_login_at: "2026-03-23T09:00:00Z",
                        },
                        {
                            id: 2,
                            strava_athlete_id: 200,
                            display_name: "Second Athlete",
                            email: null,
                            is_active: true,
                            created_at: "2026-03-21T09:00:00Z",
                            updated_at: "2026-03-23T09:00:00Z",
                            last_login_at: "2026-03-22T09:00:00Z",
                        },
                    ],
                }));
            }
            if (url.includes("/admin/users/2/disable")) {
                expect(init?.method).toBe("POST");
                return Promise.resolve({
                    ok: true,
                    status: 204,
                    headers: {get: vi.fn().mockReturnValue(null)},
                    json: vi.fn(),
                });
            }
            return Promise.reject(new Error(`Unhandled fetch: ${url}`));
        });

        render(<App/>);

        expect(await screen.findByRole("heading", {name: /dashboard/i})).toBeInTheDocument();
        expect(screen.getByRole("button", {name: /admin/i})).toBeInTheDocument();

        fireEvent.click(screen.getByRole("button", {name: /admin/i}));

        expect(await screen.findByText("Second Athlete")).toBeInTheDocument();
        expect(screen.queryAllByRole("button", {name: "Admin"})).toHaveLength(1);

        fireEvent.click(screen.getByRole("button", {name: "Reject"}));

        await waitFor(() => {
            expect(global.fetch).toHaveBeenCalledWith(
                expect.stringContaining("/admin/users/2/disable"),
                expect.objectContaining({method: "POST"}),
            );
        });
        expect(await screen.findByText("Disabled")).toBeInTheDocument();
    });

    it("does not show the admin page for a normal athlete", async () => {
        vi.spyOn(global, "fetch")
            .mockResolvedValueOnce(
                jsonResponse({
                    id: 1,
                    strava_athlete_id: 99,
                    display_name: "Test Athlete",
                    profile_picture_url: null,
                }),
            )
            .mockResolvedValueOnce(jsonResponse({status: "idle"}))
            .mockResolvedValueOnce(jsonResponse({month: [], year: []}))
            .mockResolvedValueOnce(jsonResponse({items: []}))
            .mockResolvedValueOnce(jsonResponse({items: []}))
            .mockResolvedValueOnce(jsonResponse([]))
            .mockResolvedValueOnce(jsonResponse({period_type: "month", items: []}));

        render(<App/>);

        expect(await screen.findByRole("heading", {name: /dashboard/i})).toBeInTheDocument();
        expect(screen.queryByRole("button", {name: /admin/i})).not.toBeInTheDocument();
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
                    items: [
                        {
                            effective_from: "2026-03-01",
                            aet_heart_rate_bpm: 145,
                            ant_heart_rate_bpm: 168,
                            aet_pace_min_per_km: "5.40",
                            ant_pace_min_per_km: "4.30",
                        },
                    ],
                    current: {
                        effective_from: "2026-03-01",
                        aet_heart_rate_bpm: 145,
                        ant_heart_rate_bpm: 168,
                        aet_pace_min_per_km: "5.40",
                        ant_pace_min_per_km: "4.30",
                    },
                }),
            )
            .mockResolvedValueOnce(
                jsonResponse({
                    items: [
                        {
                            effective_from: "2026-03-01",
                            aet_heart_rate_bpm: 148,
                            ant_heart_rate_bpm: 170,
                            aet_pace_min_per_km: "5.20",
                            ant_pace_min_per_km: "4.10",
                        },
                    ],
                    current: {
                        effective_from: "2026-03-01",
                        aet_heart_rate_bpm: 148,
                        ant_heart_rate_bpm: 170,
                        aet_pace_min_per_km: "5.20",
                        ant_pace_min_per_km: "4.10",
                    },
                }),
            );

        render(<App/>);

        fireEvent.click(await screen.findByRole("button", {name: /settings/i}));

        const aerobicPaceInput = await screen.findByLabelText("Aerobic Threshold Pace (min/km)");
        expect(screen.getByLabelText("Effective From")).toHaveValue("2026-03-01");
        expect(screen.getByRole("button", {name: /create new period/i})).toBeInTheDocument();
        expect(screen.getByRole("heading", {name: /edit thresholds/i})).toBeInTheDocument();
        expect(screen.getByRole("button", {name: /refresh sync/i})).toBeInTheDocument();
        expect(screen.queryByText(/latest sync/i)).not.toBeInTheDocument();
        expect(screen.getByLabelText("Aerobic Threshold HR (bpm)")).toHaveValue(145);
        expect(screen.getByLabelText("Aerobic Threshold Pace (min/km)")).toHaveValue("5:24");
        expect(screen.queryByText(/old periods stay in history automatically/i)).not.toBeInTheDocument();
        expect(screen.queryByText(/change the values below/i)).not.toBeInTheDocument();
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
                    headers: expect.objectContaining({
                        "X-Request-ID": expect.any(String),
                    }),
                    body: JSON.stringify({
                        effective_from: "2026-03-01",
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

    it("starts a new time period draft while keeping the current threshold values visible", async () => {
        vi.spyOn(global, "fetch")
            .mockResolvedValueOnce(
                jsonResponse({
                    id: 1,
                    strava_athlete_id: 99,
                    display_name: "Test Athlete",
                    profile_picture_url: null,
                }),
            )
            .mockResolvedValueOnce(jsonResponse({status: "idle"}))
            .mockResolvedValueOnce(jsonResponse({month: [], year: []}))
            .mockResolvedValueOnce(jsonResponse({items: []}))
            .mockResolvedValueOnce(jsonResponse({items: []}))
            .mockResolvedValueOnce(jsonResponse([]))
            .mockResolvedValueOnce(jsonResponse({period_type: "month", items: []}))
            .mockResolvedValueOnce(
                jsonResponse({
                    items: [
                        {
                            effective_from: "2026-03-01",
                            aet_heart_rate_bpm: 145,
                            ant_heart_rate_bpm: 168,
                            aet_pace_min_per_km: "5.40",
                            ant_pace_min_per_km: "4.30",
                        },
                    ],
                    current: {
                        effective_from: "2026-03-01",
                        aet_heart_rate_bpm: 145,
                        ant_heart_rate_bpm: 168,
                        aet_pace_min_per_km: "5.40",
                        ant_pace_min_per_km: "4.30",
                    },
                }),
            );

        render(<App/>);

        fireEvent.click(await screen.findByRole("button", {name: /settings/i}));
        expect(await screen.findByText("2026-03-01")).toBeInTheDocument();

        fireEvent.click(screen.getByRole("button", {name: /create new period/i}));

        expect(screen.getByLabelText("Effective From")).toHaveValue("");
        expect(screen.getByLabelText("Aerobic Threshold HR (bpm)")).toHaveValue(145);
        expect(screen.getByLabelText("Anaerobic Threshold Pace (min/km)")).toHaveValue("4:18");
        expect(screen.getByText("New period draft")).toBeInTheDocument();
    });

    it("ignores repeated save clicks while the profile request is in flight", async () => {
        let resolveSave;
        const savePromise = new Promise((resolve) => {
            resolveSave = resolve;
        });
        vi.spyOn(global, "fetch").mockImplementation((input, options) => {
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
                return Promise.resolve(jsonResponse({status: "idle"}));
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
            if (url.includes("/me/profile") && !options?.method) {
                return Promise.resolve(jsonResponse({
                    items: [],
                    current: null,
                }));
            }
            if (url.includes("/me/profile") && options?.method === "PUT") {
                return savePromise;
            }
            return Promise.reject(new Error(`Unhandled fetch: ${url}`));
        });

        render(<App/>);

        fireEvent.click(await screen.findByRole("button", {name: /settings/i}));
        const saveButton = await screen.findByRole("button", {name: /save profile/i});

        fireEvent.click(saveButton);
        fireEvent.click(saveButton);

        await waitFor(() => {
            expect(global.fetch).toHaveBeenCalledTimes(9);
        });

        resolveSave(jsonResponse({items: [], current: null}));
        expect(await screen.findByRole("button", {name: /save profile/i})).toBeInTheDocument();
    });
});

describe("activity detail chart baselines", () => {
    it("parses average pace and speed summary metrics", () => {
        expect(parseSummaryMetricAverage("5:00 min/km", "pace")).toBe(5);
        expect(parseSummaryMetricAverage("28 km/h", "speed")).toBe(28);
    });

    it("formats elevation axis ticks in meters", () => {
        expect(formatAltitudeAxisValue(220.4)).toBe("220 m");
        expect(formatAltitudeAxisValue(null)).toBe("");
    });

    it("formats compact detail-chart axis ticks without wrapping units", () => {
        expect(formatAxisValue("pace", 5.2)).toBe("5:12");
        expect(formatAxisValue("speed", 28.4)).toBe("28.4");
        expect(formatAxisValue("heart_rate", 150.2)).toBe("150");
        expect(formatAxisValue("slope", 0.5)).toBe("0.5");
    });

    it("shows backend error detail when saving profile settings fails", async () => {
        vi.spyOn(global, "fetch").mockImplementation((input, options) => {
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
                return Promise.resolve(jsonResponse({status: "idle"}));
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
            if (url.includes("/me/profile") && !options?.method) {
                return Promise.resolve(jsonResponse({items: [], current: null}));
            }
            if (url.includes("/me/profile") && options?.method === "PUT") {
                return Promise.resolve(jsonResponse({detail: "Threshold update failed."}, 400));
            }
            return Promise.reject(new Error(`Unhandled fetch: ${url}`));
        });

        render(<App/>);

        expect(await screen.findByRole("heading", {name: /dashboard/i})).toBeInTheDocument();

        fireEvent.click(screen.getByRole("button", {name: /settings/i}));
        expect(await screen.findByRole("button", {name: /save profile/i})).toBeInTheDocument();

        fireEvent.click(screen.getByRole("button", {name: /save profile/i}));

        expect(await screen.findByText(/threshold update failed\./i)).toBeInTheDocument();
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

    it("builds calendar summaries with dominant sport, primary activity, and scaled distance", () => {
        expect(
            buildCalendarSummary([
                {id: 10, sport_type: "Run", distance_km: 8.2},
                {id: 11, sport_type: "Ride", distance_km: 24.5},
                {id: 12, sport_type: "Ride", distance_km: 12.3},
            ]),
        ).toEqual({
            activityCount: 3,
            colorClass: "is-ride",
            distanceKm: 45,
            dominantSport: "Ride",
            primaryActivityId: 11,
            sizePx: 31,
        });
    });
});
