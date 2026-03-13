import { fireEvent, render, screen, waitFor } from "@testing-library/react";

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
          started_at: null,
          finished_at: null,
          error_message: null,
        }),
      )
      .mockResolvedValueOnce(
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
      )
      .mockResolvedValueOnce(
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
      .mockResolvedValueOnce(
        jsonResponse([
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
        ]),
      )
      .mockResolvedValueOnce(
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
              average_pace_seconds_per_km: 300,
            },
          ],
        }),
      )
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
          map: {
            polyline: [
              [50.1, 14.4],
              [50.11, 14.42],
              [50.12, 14.43],
            ],
          },
          series: {
            distance_km: [0, 5, 10],
            moving_average_heartrate: [140, 150, 155],
            moving_average_speed_kph: [11, 12, 12],
            pace_minutes_per_km: [5.2, 5.0, 4.9],
            pace_display: ["5:12", "5:00", "4:54"],
            slope_percent: [0.5, 1.2, -0.3],
          },
          intervals: [{ zone: "tempo", duration_seconds: 900 }],
          zone_summary: { tempo_minutes: 15, easy_minutes: 20 },
          compliance: { analysis_text: "Mostly tempo work.", score_text: "Score 8/10" },
          zones: [],
        }),
      );

    render(<App />);

    expect(await screen.findByRole("heading", { name: /dashboard/i })).toBeInTheDocument();
    expect(screen.getByText(/month and year snapshots/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /activities/i }));
    fireEvent.click(screen.getByRole("button", { name: /morning run/i }));

    expect(await screen.findByRole("heading", { name: /morning run/i })).toBeInTheDocument();
    expect(screen.getByText(/^distance$/i)).toBeInTheDocument();
    expect(screen.getByText(/^moving time$/i)).toBeInTheDocument();
    expect(screen.getAllByText(/^pace \/ speed$/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/^elevation$/i)).toBeInTheDocument();
    expect(screen.getByText(/^average hr$/i)).toBeInTheDocument();
    expect(screen.getByText(/running analysis/i)).toBeInTheDocument();
    expect(screen.getByText(/mostly tempo work/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/activities/11"),
        expect.objectContaining({ credentials: "include" }),
      );
    });
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
    vi.spyOn(window, "setInterval").mockImplementation((callback) => {
      intervalCallback = callback;
      return 1;
    });
    vi.spyOn(window, "clearInterval").mockImplementation(() => {});
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
          status: "running",
          sync_type: "incremental_sync",
          progress_total: 10,
          progress_completed: 1,
        }),
      )
      .mockResolvedValueOnce(jsonResponse({ month: [], year: [] }))
      .mockResolvedValueOnce(jsonResponse({ items: [] }))
      .mockResolvedValueOnce(jsonResponse({ items: [] }))
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse({ period_type: "month", items: [] }))
      .mockResolvedValueOnce(
        jsonResponse({
          status: "running",
          sync_type: "incremental_sync",
          progress_total: 10,
          progress_completed: 2,
        }),
      );

    render(<App />);

    expect(await screen.findByText("1 / 10")).toBeInTheDocument();
    expect(intervalCallback).not.toBeNull();

    await intervalCallback();

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
});
