import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";

import App from "./App";

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
    vi.spyOn(global, "fetch").mockResolvedValueOnce(jsonResponse({ detail: "Authentication required." }, 401));

    render(<App />);

    expect(await screen.findByRole("heading", { name: /local-first review for your strava history/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /continue with strava/i })).toBeInTheDocument();
  });

  it("renders dashboard data and activity detail from the backend payloads", async () => {
    vi.spyOn(global, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/auth/session")) {
        return Promise.resolve(jsonResponse({ id: 1, strava_athlete_id: 99, display_name: "Test Athlete", profile_picture_url: null }));
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
              summary_metric_display: "5:00 /km",
              total_elevation_gain_meters: 120,
              average_heartrate_bpm: 150,
              difficulty_score: 7.5,
            },
            map: { polyline: [[50.1, 14.4], [50.11, 14.42], [50.12, 14.43]] },
            series: {
              distance_km: [0, 5, 10],
              altitude_meters: [220, 260, 240],
              moving_average_heartrate: [140, 150, 155],
              moving_average_speed_kph: [11, 12, 12],
              pace_minutes_per_km: [5.2, 5.0, 4.9],
              pace_display: ["5:12", "5:00", "4:54"],
              slope_percent: [0.5, 1.2, -0.3],
            },
            intervals: [{ zone: "tempo", duration_seconds: 900 }],
            zone_summary: { tempo_minutes: 15, easy_minutes: 20 },
            compliance: { analysis_text: "Mostly tempo work.", score_text: "Score 8/10" },
            zones: [{ name: "10km", color: "#f4d44d", range_zone_pace: { lower: 4.8, upper: 5.1 }, range_zone_bpm: { lower: 148, upper: 160 } }],
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
                difficulty_score: 7.5,
              },
            ],
          }),
        );
      }
      if (url.includes("/best-efforts")) {
        return Promise.resolve(
          jsonResponse({
            items: [{ effort_code: "half_marathon", best_time_seconds: 5400, distance_meters: 21097.5, activity_id: 11, achieved_at: "2026-03-05T08:30:00" }],
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
              { sport_type: "Run", period_type: "month", period_start: "2026-03-01", activity_count: 3, total_distance_meters: 42000, total_moving_time_seconds: 12600, average_pace_seconds_per_km: 300 },
              { sport_type: "Run", period_type: "month", period_start: "2026-02-01", activity_count: 2, total_distance_meters: 30000, total_moving_time_seconds: 9600, average_pace_seconds_per_km: 320 },
            ],
          }),
        );
      }
      return Promise.reject(new Error(`Unhandled fetch: ${url}`));
    });

    render(<App />);

    expect(await screen.findByRole("heading", { name: /dashboard/i })).toBeInTheDocument();
    expect(screen.getAllByText(/^overview$/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/^selected window$/i)).not.toBeInTheDocument();
    expect((await screen.findAllByText(/03\/2026 vs 02\/2026/i)).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: /activities/i }));
    fireEvent.click(screen.getByRole("button", { name: /morning run/i }));

    expect(await screen.findByRole("heading", { name: /morning run/i })).toBeInTheDocument();
    expect(screen.getByText(/^distance$/i)).toBeInTheDocument();
    expect(screen.getByText(/^moving time$/i)).toBeInTheDocument();
    expect(screen.getAllByText(/^pace \/ speed$/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/^elevation$/i)).toBeInTheDocument();
    expect(screen.getByText(/^average hr$/i)).toBeInTheDocument();
    expect(screen.queryByText(/zone summary/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/intervals/i)).not.toBeInTheDocument();
    expect(screen.getByText(/running analysis/i)).toBeInTheDocument();
    expect(screen.getByText(/mostly tempo work/i)).toBeInTheDocument();
    expect(screen.getByLabelText("min/km chart")).toBeInTheDocument();
    expect(screen.getByLabelText("bpm chart")).toBeInTheDocument();
    expect(screen.getByLabelText("% chart")).toBeInTheDocument();

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/activities/11"),
        expect.objectContaining({ credentials: "include" }),
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
        return Promise.resolve(jsonResponse({ month: [], year: [] }));
      }
      if (url.includes("/activities")) {
        return Promise.resolve(jsonResponse({ items: [] }));
      }
      if (url.includes("/best-efforts")) {
        return Promise.resolve(jsonResponse({ items: [] }));
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
              },
              {
                sport_type: "Run",
                period_type: "month",
                period_start: "2026-02-01",
                activity_count: 4,
                total_distance_meters: 41000,
                total_moving_time_seconds: 12600,
              },
              {
                sport_type: "Run",
                period_type: "month",
                period_start: "2026-03-01",
                activity_count: 3,
                total_distance_meters: 33000,
                total_moving_time_seconds: 9900,
              },
            ],
          }),
        );
      }
      return Promise.reject(new Error(`Unhandled fetch: ${url}`));
    });

    render(<App />);

    const graph = await screen.findByLabelText(/trend graph/i);
    expect(graph).toBeInTheDocument();
    expect(screen.getByText(/^km$/i)).toBeInTheDocument();
    expect(screen.getByText(/^sessions$/i)).toBeInTheDocument();
    expect(screen.getByText(/mar 1, 2026/i)).toBeInTheDocument();
    expect(screen.getByText(/33 km/i)).toBeInTheDocument();
    expect(screen.getByText(/3 sessions/i)).toBeInTheDocument();

    graph.getBoundingClientRect = vi.fn(() => ({
      width: 300,
      height: 240,
      top: 0,
      left: 0,
      right: 300,
      bottom: 240,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    }));

    fireEvent.mouseMove(graph, { clientX: 10, clientY: 120 });

    expect(await screen.findByText(/jan 1, 2026/i)).toBeInTheDocument();
    expect(screen.getByText(/25 km/i)).toBeInTheDocument();
    expect(screen.getByText(/2 sessions/i)).toBeInTheDocument();
  });

  it("lets the user choose which two monthly periods to compare", async () => {
    vi.spyOn(global, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/auth/session")) {
        return Promise.resolve(jsonResponse({ id: 1, strava_athlete_id: 99, display_name: "Test Athlete", profile_picture_url: null }));
      }
      if (url.includes("/sync/status")) {
        return Promise.resolve(jsonResponse({ status: "completed", sync_type: "full_import", progress_total: 10, progress_completed: 10 }));
      }
      if (url.includes("/dashboard")) {
        return Promise.resolve(jsonResponse({ month: [], year: [] }));
      }
      if (url.includes("/activities")) {
        return Promise.resolve(jsonResponse({ items: [] }));
      }
      if (url.includes("/best-efforts")) {
        return Promise.resolve(jsonResponse({ items: [] }));
      }
      if (url.includes("/trends")) {
        return Promise.resolve(
          jsonResponse({
            period_type: "month",
            items: [
              { sport_type: "Run", period_type: "month", period_start: "2026-01-01", activity_count: 2, total_distance_meters: 25000, total_moving_time_seconds: 7200 },
              { sport_type: "Run", period_type: "month", period_start: "2026-02-01", activity_count: 4, total_distance_meters: 41000, total_moving_time_seconds: 12600 },
              { sport_type: "Run", period_type: "month", period_start: "2026-03-01", activity_count: 3, total_distance_meters: 33000, total_moving_time_seconds: 9900 },
            ],
          }),
        );
      }
      if (url.includes("/comparisons")) {
        return Promise.resolve(jsonResponse([]));
      }
      return Promise.reject(new Error(`Unhandled fetch: ${url}`));
    });

    render(<App />);

    expect(await screen.findByDisplayValue("03/2026")).toBeInTheDocument();
    expect(screen.getByDisplayValue("02/2026")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/current/i), { target: { value: "2026-02-01" } });
    fireEvent.change(screen.getByLabelText(/previous/i), { target: { value: "2026-01-01" } });

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/comparisons?period_type=month&current_period_start=2026-02-01&previous_period_start=2026-01-01"),
        expect.objectContaining({ credentials: "include" }),
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
      .mockResolvedValueOnce(jsonResponse({ month: [], year: [] }))
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
      .mockResolvedValueOnce(jsonResponse({ period_type: "month", items: [] }))
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
            summary_metric_display: "5:00 /km",
            total_elevation_gain_meters: 120,
            average_heartrate_bpm: 150,
            difficulty_score: 7.5,
          },
          map: { polyline: [[50.1, 14.4], [50.11, 14.42]] },
          series: {
            distance_km: [0, 5, 10],
            altitude_meters: [220, 260, 240],
            moving_average_heartrate: [140, 150, 155],
            moving_average_speed_kph: [11, 12, 12],
            pace_minutes_per_km: [5.2, 5.0, 4.9],
            pace_display: ["5:12", "5:00", "4:54"],
            slope_percent: [0.5, 1.2, -0.3],
          },
          intervals: [],
          zone_summary: {},
          compliance: { analysis_text: "Mostly tempo work.", score_text: "Score 8/10" },
          zones: [],
        }),
      );

    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: /best efforts/i }));
    fireEvent.click(await screen.findByRole("button", { name: /half marathon/i }));

    expect(await screen.findByRole("heading", { name: /morning run/i })).toBeInTheDocument();
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
      .mockResolvedValueOnce(jsonResponse({ month: [], year: [] }))
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
      .mockResolvedValueOnce(jsonResponse({ items: [] }))
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse({ period_type: "month", items: [] }));

    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: /calendar/i }));

    expect(await screen.findByText(/2 activities/i)).toBeInTheDocument();
    const bubble = screen.getByRole("button", { name: /15 km/i });
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
      .mockResolvedValueOnce(jsonResponse({ month: [], year: [] }))
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
      .mockResolvedValueOnce(jsonResponse({ items: [] }))
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse({ period_type: "month", items: [] }));

    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: /calendar/i }));

    const bubble = await screen.findByRole("button", { name: /42 km/i });
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
      .mockResolvedValueOnce(jsonResponse({ month: [], year: [] }))
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
      .mockResolvedValueOnce(jsonResponse({ items: [] }))
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse({ period_type: "month", items: [] }));

    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: /calendar/i }));

    const shortBubble = await screen.findByRole("button", { name: /^8 km$/i });
    const mediumBubble = await screen.findByRole("button", { name: /^18 km$/i });
    const longBubble = await screen.findByRole("button", { name: /^30 km$/i });

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
      .mockResolvedValueOnce(jsonResponse({ month: [], year: [] }))
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
      .mockResolvedValueOnce(jsonResponse({ items: [] }))
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse({ period_type: "month", items: [] }));

    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: /calendar/i }));

    const shortRideBubble = await screen.findByRole("button", { name: /^20 km$/i });
    const longRideBubble = await screen.findByRole("button", { name: /^100 km$/i });

    expect(shortRideBubble.style.getPropertyValue("--bubble-size")).toBe("33px");
    expect(longRideBubble.style.getPropertyValue("--bubble-size")).toBe("53px");
  });

  it("updates sync progress while a sync is running without a manual reload", async () => {
    let intervalCallback = null;
    let syncPollCount = 0;
    vi.spyOn(window, "setInterval").mockImplementation((callback) => {
      intervalCallback = callback;
      return 1;
    });
    vi.spyOn(window, "clearInterval").mockImplementation(() => {});
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
      if (url.includes("/dashboard/comparisons")) {
        return Promise.resolve(jsonResponse({ month: [], year: [] }));
      }
      if (url.endsWith("/dashboard")) {
        return Promise.resolve(
          jsonResponse({
            summary: [],
            highlights: [],
            selected_window: [],
          }),
        );
      }
      if (url.includes("/activities")) {
        return Promise.resolve(jsonResponse({ items: [] }));
      }
      if (url.includes("/best-efforts")) {
        return Promise.resolve(jsonResponse({ items: [] }));
      }
      if (url.includes("/calendar")) {
        return Promise.resolve(jsonResponse([]));
      }
      if (url.includes("/dashboard/trends")) {
        return Promise.resolve(jsonResponse({ period_type: "month", items: [] }));
      }
      if (url.includes("/me/profile")) {
        return Promise.resolve(
          jsonResponse({
            birthday: "",
            speed_max: null,
            max_heart_rate_override: null,
          }),
        );
      }
      throw new Error(`Unhandled fetch request in test: ${url}`);
    });

    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: /settings/i }));

    expect(await screen.findByText("1 / 10")).toBeInTheDocument();
    expect(intervalCallback).not.toBeNull();

    await act(async () => {
      await intervalCallback();
    });

    expect(await screen.findByText("2 / 10")).toBeInTheDocument();
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
      .mockResolvedValueOnce(jsonResponse({ month: [], year: [] }))
      .mockResolvedValueOnce(jsonResponse({ items: [] }))
      .mockResolvedValueOnce(jsonResponse({ items: [] }))
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse({ period_type: "month", items: [] }));

    render(<App />);

    expect(await screen.findByRole("heading", { name: /dashboard/i })).toBeInTheDocument();
    expect(screen.getByText("Sport")).toBeInTheDocument();
    expect(screen.getByText("Window")).toBeInTheDocument();
    expect(screen.queryByText("From")).not.toBeInTheDocument();
    expect(screen.queryByText("To")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /activities/i }));
    expect(await screen.findByRole("heading", { name: /activities/i })).toBeInTheDocument();
    expect(screen.getByText("Sport")).toBeInTheDocument();
    expect(screen.getByText("From")).toBeInTheDocument();
    expect(screen.getByText("To")).toBeInTheDocument();
    expect(screen.queryByText("Window")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /calendar/i }));
    expect(await screen.findByRole("heading", { name: /calendar/i })).toBeInTheDocument();
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
      .mockResolvedValueOnce(jsonResponse({ month: [], year: [] }))
      .mockResolvedValueOnce(jsonResponse({ items: [] }))
      .mockResolvedValueOnce(jsonResponse({ items: [] }))
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse({ period_type: "month", items: [] }))
      .mockResolvedValueOnce(
        jsonResponse({
          birthday: "1990-01-01",
          speed_max: "15.50",
          max_heart_rate_override: null,
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          birthday: "1990-01-01",
          speed_max: "16.20",
          max_heart_rate_override: 188,
        }),
      );

    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: /settings/i }));

    const paceInput = await screen.findByLabelText("Max Aerobic Pace (min/km)");
    expect(screen.getByRole("button", { name: /refresh sync/i })).toBeInTheDocument();
    expect(screen.queryByText(/latest sync/i)).not.toBeInTheDocument();
    expect(paceInput).toHaveValue("3:52");
    expect(screen.queryByText(/session model/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/profile image/i)).not.toBeInTheDocument();
    fireEvent.change(paceInput, { target: { value: "3:42" } });
    fireEvent.change(screen.getByLabelText("Max HR Override"), { target: { value: "188" } });
    fireEvent.click(screen.getByRole("button", { name: /save profile/i }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/me/profile"),
        expect.objectContaining({
          body: JSON.stringify({
            birthday: "1990-01-01",
            max_heart_rate_override: 188,
            speed_max: 16.22,
          }),
          method: "PUT",
        }),
      );
    });
  });
});
