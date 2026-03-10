import { startTransition, useEffect, useMemo, useRef, useState } from "react";
import "leaflet/dist/leaflet.css";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const views = ["dashboard", "calendar", "activities", "best-efforts", "settings"];
const windows = [
  { id: "week", label: "Week" },
  { id: "month", label: "Month" },
  { id: "year", label: "Year" },
  { id: "rolling_30d", label: "30 Days" },
];
const sports = [
  { id: "", label: "All Sports" },
  { id: "Run", label: "Run" },
  { id: "Ride", label: "Ride" },
  { id: "EBikeRide", label: "E-Bike" },
];

export default function App() {
  const [sessionState, setSessionState] = useState("loading");
  const [user, setUser] = useState(null);
  const [syncStatus, setSyncStatus] = useState(null);
  const [dashboard, setDashboard] = useState(null);
  const [comparisons, setComparisons] = useState([]);
  const [trends, setTrends] = useState(null);
  const [activities, setActivities] = useState([]);
  const [bestEfforts, setBestEfforts] = useState([]);
  const [selectedView, setSelectedView] = useState("dashboard");
  const [selectedWindow, setSelectedWindow] = useState("month");
  const [selectedSport, setSelectedSport] = useState("");
  const [selectedActivityId, setSelectedActivityId] = useState(null);
  const [activityDetail, setActivityDetail] = useState(null);
  const [activityDetailState, setActivityDetailState] = useState("idle");
  const [calendarMonth, setCalendarMonth] = useState(startOfMonth(new Date()));
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [activeSeriesIndex, setActiveSeriesIndex] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [authBusy, setAuthBusy] = useState(false);
  const [syncBusy, setSyncBusy] = useState(false);

  const activityQuery = useMemo(
    () =>
      buildQuery({
        sport_type: selectedSport || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      }),
    [dateFrom, dateTo, selectedSport],
  );

  useEffect(() => {
    let active = true;
    async function bootstrap() {
      try {
        const session = await fetchJson("/auth/session");
        if (!active) {
          return;
        }
        startTransition(() => {
          setUser(session);
          setSessionState("authenticated");
        });
      } catch (error) {
        if (!active) {
          return;
        }
        if (error.status === 401) {
          setSessionState("anonymous");
          return;
        }
        setErrorMessage(error.message ?? "Failed to initialize the app.");
        setSessionState("anonymous");
      }
    }
    bootstrap();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (sessionState !== "authenticated") {
      return;
    }
    let active = true;
    async function loadData() {
      try {
        const [sync, overview, activityList, efforts, comparisonItems, trendItems] = await Promise.all([
          fetchJson("/sync/status"),
          fetchJson(`/dashboard${buildQuery({ sport_type: selectedSport || undefined })}`),
          fetchJson(`/activities${activityQuery}`),
          fetchJson(`/best-efforts${buildQuery({ sport_type: selectedSport || "Run" })}`),
          fetchJson(
            `/comparisons${buildQuery({
              period_type: selectedWindow,
              sport_type: selectedSport || undefined,
            })}`,
          ),
          selectedWindow === "rolling_30d"
            ? Promise.resolve(null)
            : fetchJson(
                `/trends${buildQuery({
                  period_type: selectedWindow,
                  sport_type: selectedSport || undefined,
                })}`,
              ),
        ]);

        if (!active) {
          return;
        }
        startTransition(() => {
          setSyncStatus(sync);
          setDashboard(overview);
          setActivities(activityList.items ?? []);
          setBestEfforts(efforts.items ?? []);
          setComparisons(comparisonItems ?? []);
          setTrends(trendItems);
          setErrorMessage("");
        });
      } catch (error) {
        if (active) {
          setErrorMessage(error.message ?? "Failed to load application data.");
        }
      }
    }
    loadData();
    return () => {
      active = false;
    };
  }, [activityQuery, selectedSport, selectedWindow, sessionState]);

  useEffect(() => {
    if (sessionState !== "authenticated" || selectedActivityId == null) {
      return;
    }
    let active = true;
    setActivityDetailState("loading");
    fetchJson(`/activities/${selectedActivityId}`)
      .then((payload) => {
        if (!active) {
          return;
        }
        setActivityDetail(payload);
        setActivityDetailState("ready");
      })
      .catch((error) => {
        if (active) {
          setActivityDetailState("error");
          setErrorMessage(error.message ?? "Failed to load activity detail.");
        }
      });
    return () => {
      active = false;
    };
  }, [selectedActivityId, sessionState]);

  async function handleLogin() {
    try {
      setAuthBusy(true);
      const payload = await fetchJson("/auth/strava/login");
      window.location.assign(payload.authorization_url);
    } catch (error) {
      setErrorMessage(error.message ?? "Failed to start Strava login.");
    } finally {
      setAuthBusy(false);
    }
  }

  async function handleLogout() {
    try {
      await fetchJson("/auth/logout", { method: "POST" });
      setSessionState("anonymous");
      setUser(null);
      setActivityDetail(null);
      setSelectedActivityId(null);
      setActivityDetailState("idle");
    } catch (error) {
      setErrorMessage(error.message ?? "Failed to log out.");
    }
  }

  async function handleRefreshSync() {
    try {
      setSyncBusy(true);
      await fetchJson("/sync/refresh", { method: "POST" });
      setSyncStatus(await fetchJson("/sync/status"));
      setErrorMessage("");
    } catch (error) {
      setErrorMessage(error.message ?? "Failed to trigger sync.");
    } finally {
      setSyncBusy(false);
    }
  }

  if (sessionState === "loading") {
    return <LoadingScreen />;
  }

  if (sessionState === "anonymous") {
    return <LandingScreen authBusy={authBusy} errorMessage={errorMessage} onLogin={handleLogin} />;
  }

  return (
    <main className="app-shell">
      <AmbientBackdrop />
      <div className="app-frame">
        <Sidebar
          selectedView={selectedView}
          syncStatus={syncStatus}
          user={user}
          onLogout={handleLogout}
          onSelectView={setSelectedView}
        />
        <section className="workspace">
          <Toolbar
            dateFrom={dateFrom}
            dateTo={dateTo}
            selectedSport={selectedSport}
            selectedView={selectedView}
            selectedWindow={selectedWindow}
            syncBusy={syncBusy}
            onChangeDateFrom={setDateFrom}
            onChangeDateTo={setDateTo}
            onRefresh={handleRefreshSync}
            onSelectSport={setSelectedSport}
            onSelectWindow={setSelectedWindow}
          />
          {errorMessage ? <div className="banner-error">{errorMessage}</div> : null}
          {selectedView === "dashboard" ? (
            <DashboardView comparisons={comparisons} dashboard={dashboard} trends={trends} />
          ) : null}
          {selectedView === "calendar" ? (
            <CalendarView
              activities={activities}
              calendarMonth={calendarMonth}
              onChangeMonth={setCalendarMonth}
              onSelectActivity={(id) => {
                setSelectedActivityId(id);
                setSelectedView("activities");
              }}
            />
          ) : null}
          {selectedView === "activities" ? (
            <ActivitiesView
              activities={activities}
              activeSeriesIndex={activeSeriesIndex}
              activityDetail={activityDetail}
              detailState={activityDetailState}
              selectedActivityId={selectedActivityId}
              onHoverIndex={setActiveSeriesIndex}
              onSelectActivity={setSelectedActivityId}
            />
          ) : null}
          {selectedView === "best-efforts" ? <BestEffortsView items={bestEfforts} /> : null}
          {selectedView === "settings" ? (
            <SettingsView syncStatus={syncStatus} user={user} onLogout={handleLogout} />
          ) : null}
        </section>
      </div>
    </main>
  );
}

function LoadingScreen() {
  return (
    <main className="app-shell loading-state">
      <AmbientBackdrop />
      <div className="loading-card">
        <p className="eyebrow">Strava Insights</p>
        <h1>Connecting to your local training archive.</h1>
        <p className="copy">Reading session and cached summaries.</p>
      </div>
    </main>
  );
}

function LandingScreen({ authBusy, errorMessage, onLogin }) {
  return (
    <main className="app-shell landing-shell">
      <AmbientBackdrop />
      <section className="landing-panel">
        <div className="landing-copy">
          <p className="eyebrow">Strava Insights</p>
          <h1>Local-first review for your Strava history.</h1>
          <p className="copy">
            Authenticate once, import your archive into PostgreSQL, and review calendar, best
            efforts, comparisons, and backend-driven activity analytics.
          </p>
          {errorMessage ? <p className="banner-error">{errorMessage}</p> : null}
          <button className="primary-button" disabled={authBusy} onClick={onLogin} type="button">
            {authBusy ? "Opening Strava..." : "Continue with Strava"}
          </button>
        </div>
        <div className="landing-metrics">
          <MetricTile label="Comparison Windows" value="Week / Month / Year / 30d" />
          <MetricTile label="Read Model" value="Cached + DB-backed" />
          <MetricTile label="Activity Detail" value="Pace, slope, HR, zones" />
        </div>
      </section>
    </main>
  );
}

function Sidebar({ selectedView, syncStatus, user, onLogout, onSelectView }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-user">
        <p className="eyebrow">Athlete</p>
        <h2 className="sidebar-title">{user.display_name}</h2>
        <p className="sidebar-subtle">Strava ID {user.strava_athlete_id}</p>
      </div>
      <nav aria-label="Primary" className="sidebar-nav">
        {views.map((view) => (
          <button
            key={view}
            className={view === selectedView ? "nav-pill active" : "nav-pill"}
            onClick={() => onSelectView(view)}
            type="button"
          >
            {formatLabel(view)}
          </button>
        ))}
      </nav>
      <div className="sync-card">
        <p className="eyebrow">Latest Sync</p>
        <strong>{formatLabel(syncStatus?.status ?? "idle")}</strong>
        <p className="sidebar-subtle">{formatSyncProgress(syncStatus)}</p>
      </div>
      <button className="ghost-button sidebar-logout" onClick={onLogout} type="button">
        Log out
      </button>
    </aside>
  );
}

function Toolbar({
  dateFrom,
  dateTo,
  selectedSport,
  selectedView,
  selectedWindow,
  syncBusy,
  onChangeDateFrom,
  onChangeDateTo,
  onRefresh,
  onSelectSport,
  onSelectWindow,
}) {
  return (
    <header className="toolbar">
      <div>
        <p className="eyebrow">Review Surface</p>
        <h1 className="toolbar-title">{formatLabel(selectedView)}</h1>
      </div>
      <div className="toolbar-controls">
        <FilterSelect label="Sport" options={sports} value={selectedSport} onChange={onSelectSport} />
        <FilterSelect label="Window" options={windows} value={selectedWindow} onChange={onSelectWindow} />
        <FilterDate label="From" value={dateFrom} onChange={onChangeDateFrom} />
        <FilterDate label="To" value={dateTo} onChange={onChangeDateTo} />
        <button className="ghost-button" disabled={syncBusy} onClick={onRefresh} type="button">
          {syncBusy ? "Refreshing..." : "Refresh Sync"}
        </button>
      </div>
    </header>
  );
}

function FilterSelect({ label, options, value, onChange }) {
  return (
    <label className="control-chip">
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => (
          <option key={option.id} value={option.id}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function FilterDate({ label, value, onChange }) {
  return (
    <label className="control-chip">
      <span>{label}</span>
      <input type="date" value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function DashboardView({ comparisons, dashboard, trends }) {
  const snapshotCards = [...(dashboard?.month ?? []), ...(dashboard?.year ?? [])];
  return (
    <section className="panel-grid">
      <article className="panel panel-span-two">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Overview</p>
            <h2>Month and year snapshots</h2>
          </div>
        </div>
        <div className="comparison-grid">
          {snapshotCards.map((comparison, index) => (
            <ComparisonCard
              key={`${comparison.current?.sport_type ?? comparison.previous?.sport_type ?? "unknown"}-${index}`}
              comparison={comparison}
            />
          ))}
        </div>
      </article>
      <article className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Selected Window</p>
            <h2>Comparison view</h2>
          </div>
        </div>
        <div className="comparison-grid single-column">
          {comparisons.length === 0 ? <EmptyState text="No comparison data yet." /> : null}
          {comparisons.map((comparison, index) => (
            <ComparisonCard
              key={`${comparison.current?.sport_type ?? comparison.previous?.sport_type ?? "selected"}-${index}`}
              comparison={comparison}
            />
          ))}
        </div>
      </article>
      <article className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Trend Series</p>
            <h2>{trends ? formatLabel(trends.period_type) : "Rolling 30d"}</h2>
          </div>
        </div>
        {trends ? <TrendList items={trends.items} /> : <EmptyState text="Rolling 30-day mode compares windows directly." />}
      </article>
    </section>
  );
}

function CalendarView({ activities, calendarMonth, onChangeMonth, onSelectActivity }) {
  const days = useMemo(() => buildCalendarDays(calendarMonth, activities), [activities, calendarMonth]);
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Calendar</p>
          <h2>{calendarMonth.toLocaleDateString(undefined, { month: "long", year: "numeric" })}</h2>
        </div>
        <div className="calendar-controls">
          <button className="ghost-button" onClick={() => onChangeMonth(shiftMonth(calendarMonth, -1))} type="button">
            Prev
          </button>
          <button className="ghost-button" onClick={() => onChangeMonth(shiftMonth(calendarMonth, 1))} type="button">
            Next
          </button>
        </div>
      </div>
      <div className="calendar-grid">
        {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day) => (
          <div className="calendar-head" key={day}>
            {day}
          </div>
        ))}
        {days.map((day) => (
          <div
            key={formatLocalDateKey(day.date)}
            className={day.isCurrentMonth ? "calendar-cell" : "calendar-cell muted"}
          >
            <div className="calendar-date">{day.date.getDate()}</div>
            <div className="calendar-events">
              {day.summary ? (
                <button
                  className={`calendar-bubble ${day.summary.colorClass}`}
                  onClick={() => onSelectActivity(day.summary.primaryActivityId)}
                  style={{ "--bubble-size": `${day.summary.sizePx}px` }}
                  type="button"
                >
                  <span className="calendar-bubble-distance">{formatNumber(day.summary.distanceKm)}</span>
                  <span className="calendar-bubble-unit">km</span>
                </button>
              ) : (
                <div className="calendar-bubble calendar-bubble-empty" />
              )}
              {day.summary ? (
                <div className="calendar-summary">
                  <strong>{formatLabel(day.summary.dominantSport)}</strong>
                  <span>{day.summary.activityCount} activities</span>
                </div>
              ) : (
                <div className="calendar-summary empty">Rest day</div>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function ActivitiesView({
  activities,
  activeSeriesIndex,
  activityDetail,
  detailState,
  selectedActivityId,
  onHoverIndex,
  onSelectActivity,
}) {
  return (
    <section className="activities-layout">
      <article className="panel activity-list-panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Activities</p>
            <h2>Imported sessions</h2>
          </div>
        </div>
        <div className="activity-list">
          {activities.length === 0 ? <EmptyState text="No activities imported yet." /> : null}
          {activities.map((activity) => (
            <button
              key={activity.id}
              className={selectedActivityId === activity.id ? "activity-row active" : "activity-row"}
              onClick={() => onSelectActivity(activity.id)}
              type="button"
            >
              <div>
                <strong>{activity.name}</strong>
                <p>{activity.sport_type}</p>
              </div>
              <div className="activity-row-kpis">
                <span>{activity.distance_km ?? "?"} km</span>
                <span>{activity.summary_metric_display ?? "n/a"}</span>
              </div>
            </button>
          ))}
        </div>
      </article>
      <article className="panel activity-detail-panel">
        {detailState === "idle" ? <EmptyState text="Select an activity to inspect the detail payload." /> : null}
        {detailState === "loading" ? <EmptyState text="Loading activity detail..." /> : null}
        {detailState === "error" ? <EmptyState text="Activity detail failed to load." /> : null}
        {detailState === "ready" && activityDetail ? (
          <ActivityDetail detail={activityDetail} activeSeriesIndex={activeSeriesIndex} onHoverIndex={onHoverIndex} />
        ) : null}
      </article>
    </section>
  );
}

function ActivityDetail({ detail, activeSeriesIndex, onHoverIndex }) {
  const routePoints = detail.map?.polyline ?? [];
  const paceOrSpeed = detail.series.pace_minutes_per_km.length
    ? detail.series.pace_minutes_per_km
    : detail.series.moving_average_speed_kph;

  return (
    <div className="activity-detail">
      <div className="panel-header">
        <div>
          <p className="eyebrow">{detail.sport_type}</p>
          <h2>{detail.name}</h2>
        </div>
        <p className="sidebar-subtle">{detail.start_date_local ? formatDateTime(detail.start_date_local) : ""}</p>
      </div>
      <div className="kpi-grid">
        <MetricTile label="Distance" value={detail.kpis.distance_km != null ? `${detail.kpis.distance_km} km` : "n/a"} />
        <MetricTile label="Moving Time" value={detail.kpis.moving_time_display ?? "n/a"} />
        <MetricTile label="Pace / Speed" value={detail.kpis.summary_metric_display ?? "n/a"} />
        <MetricTile label="Elevation" value={detail.kpis.total_elevation_gain_meters != null ? `${detail.kpis.total_elevation_gain_meters} m` : "n/a"} />
        <MetricTile label="Average HR" value={detail.kpis.average_heartrate_bpm != null ? `${detail.kpis.average_heartrate_bpm} bpm` : "n/a"} />
      </div>
      <div className="detail-grid">
        <div className="detail-card detail-card-wide">
          <p className="eyebrow">Route</p>
          <MapPanel activeIndex={activeSeriesIndex} polyline={routePoints} />
        </div>
        <DetailChart accent="orange" label="Pace / Speed" values={paceOrSpeed} activeIndex={activeSeriesIndex} onHoverIndex={onHoverIndex} />
        <DetailChart accent="red" label="Heart Rate" values={detail.series.moving_average_heartrate} activeIndex={activeSeriesIndex} onHoverIndex={onHoverIndex} />
        <DetailChart accent="green" label="Slope" values={detail.series.slope_percent} activeIndex={activeSeriesIndex} onHoverIndex={onHoverIndex} />
      </div>
      <div className="detail-analysis-grid">
        <div className="detail-card">
          <p className="eyebrow">Zone Summary</p>
          <KeyValueList data={detail.zone_summary} emptyText="No zone summary available." />
        </div>
        <div className="detail-card">
          <p className="eyebrow">Intervals</p>
          <IntervalList intervals={detail.intervals} />
        </div>
        <div className="detail-card">
          <p className="eyebrow">Running Analysis</p>
          {detail.compliance ? (
            <>
              <strong>{detail.compliance.analysis_text ?? "Compliance summary available."}</strong>
              <p className="sidebar-subtle">{detail.compliance.score_text ?? ""}</p>
            </>
          ) : (
            <EmptyState compact text="No running compliance summary available for this activity." />
          )}
        </div>
      </div>
    </div>
  );
}

function DetailChart({ accent, label, values, activeIndex, onHoverIndex }) {
  return (
    <div className="detail-card">
      <p className="eyebrow">{label}</p>
      <MiniLineChart accent={accent} activeIndex={activeIndex} values={values} onHoverIndex={onHoverIndex} />
    </div>
  );
}

function BestEffortsView({ items }) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Best Efforts</p>
          <h2>Running marks</h2>
        </div>
      </div>
      <div className="best-effort-grid">
        {items.length === 0 ? <EmptyState text="No best efforts stored yet." /> : null}
        {items.map((item) => (
          <div key={item.effort_code} className="best-effort-card">
            <strong>{formatLabel(item.effort_code)}</strong>
            <span>{formatDuration(item.best_time_seconds)}</span>
            <p>{formatDistanceMeters(item.distance_meters)}</p>
            <small>{item.achieved_at ? formatDateLabel(item.achieved_at) : "Imported best mark"}</small>
          </div>
        ))}
      </div>
    </section>
  );
}

function SettingsView({ syncStatus, user, onLogout }) {
  return (
    <section className="panel-grid">
      <article className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Profile</p>
            <h2>{user.display_name}</h2>
          </div>
        </div>
        <div className="settings-list">
          <div className="settings-row"><span>Strava Athlete</span><strong>{user.strava_athlete_id}</strong></div>
          <div className="settings-row"><span>Session Model</span><strong>Cookie-based</strong></div>
          <div className="settings-row"><span>Profile Image</span><strong>{user.profile_picture_url ? "Available" : "Not set"}</strong></div>
        </div>
        <button className="ghost-button inline-button" onClick={onLogout} type="button">Log out</button>
      </article>
      <article className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Sync Status</p>
            <h2>{formatLabel(syncStatus?.status ?? "idle")}</h2>
          </div>
        </div>
        <div className="settings-list">
          <div className="settings-row"><span>Type</span><strong>{syncStatus?.sync_type ?? "n/a"}</strong></div>
          <div className="settings-row"><span>Progress</span><strong>{formatSyncProgress(syncStatus)}</strong></div>
          <div className="settings-row"><span>Started</span><strong>{syncStatus?.started_at ? formatDateTime(syncStatus.started_at) : "n/a"}</strong></div>
          <div className="settings-row"><span>Finished</span><strong>{syncStatus?.finished_at ? formatDateTime(syncStatus.finished_at) : "n/a"}</strong></div>
        </div>
      </article>
    </section>
  );
}

function ComparisonCard({ comparison }) {
  const current = comparison.current;
  const previous = comparison.previous;
  const isPace = current?.average_pace_seconds_per_km != null || previous?.average_pace_seconds_per_km != null;
  return (
    <div className="comparison-card">
      <div className="comparison-heading">
        <strong>{current?.sport_type ?? previous?.sport_type ?? "Unknown"}</strong>
        <span>{formatLabel(current?.period_type ?? previous?.period_type ?? "period")}</span>
      </div>
      <MetricRow label="Distance" current={current?.total_distance_meters} previous={previous?.total_distance_meters} renderValue={formatDistanceMeters} />
      <MetricRow label="Moving Time" current={current?.total_moving_time_seconds} previous={previous?.total_moving_time_seconds} renderValue={formatDuration} />
      <MetricRow label="Activity Count" current={current?.activity_count} previous={previous?.activity_count} />
      <MetricRow
        label={isPace ? "Average Pace" : "Average Speed"}
        current={current?.average_pace_seconds_per_km ?? current?.average_speed_mps}
        previous={previous?.average_pace_seconds_per_km ?? previous?.average_speed_mps}
        renderValue={isPace ? formatPaceSeconds : (value) => formatMetricValue(value, "m/s")}
      />
    </div>
  );
}

function TrendList({ items }) {
  if (!items.length) {
    return <EmptyState text="No trend points yet." />;
  }
  return (
    <div className="trend-list">
      {items.map((item) => (
        <div key={`${item.sport_type}-${item.period_start}`} className="trend-row">
          <div>
            <strong>{item.sport_type}</strong>
            <p>{formatDateLabel(item.period_start)}</p>
          </div>
          <div className="trend-metrics">
            <span>{formatDistanceMeters(item.total_distance_meters)}</span>
            <span>{item.activity_count} sessions</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function MetricTile({ label, value }) {
  return (
    <div className="metric-tile">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function MetricRow({ label, current, previous, renderValue = formatMetricValue }) {
  return (
    <div className="metric-row">
      <span>{label}</span>
      <strong>
        {renderValue(current)}
        {previous != null ? <em>vs {renderValue(previous)}</em> : null}
      </strong>
    </div>
  );
}

function KeyValueList({ data, emptyText }) {
  const items = Object.entries(data ?? {});
  if (!items.length) {
    return <EmptyState compact text={emptyText} />;
  }
  return (
    <div className="summary-list">
      {items.map(([key, value]) => (
        <div className="summary-row" key={key}>
          <span>{formatLabel(key)}</span>
          <strong>{formatAny(value)}</strong>
        </div>
      ))}
    </div>
  );
}

function IntervalList({ intervals }) {
  if (!intervals?.length) {
    return <EmptyState compact text="No interval groups detected." />;
  }
  return (
    <div className="interval-list">
      {intervals.slice(0, 8).map((interval, index) => (
        <div className="interval-row" key={`${interval.zone ?? "interval"}-${index}`}>
          <span>{formatLabel(interval.zone ?? interval.label ?? `interval ${index + 1}`)}</span>
          <strong>{interval.duration_seconds ? formatDuration(interval.duration_seconds) : formatAny(interval.count ?? interval.duration)}</strong>
        </div>
      ))}
    </div>
  );
}

function MiniLineChart({ accent, activeIndex, values, onHoverIndex }) {
  if (!values?.length) {
    return <EmptyState compact text="No series available." />;
  }
  const normalized = normalizeSeries(values);
  const points = normalized
    .map((value, index) => `${(index / Math.max(values.length - 1, 1)) * 100},${100 - value * 100}`)
    .join(" ");
  const markerX = activeIndex == null ? null : (activeIndex / Math.max(values.length - 1, 1)) * 100;
  const markerY = activeIndex == null ? null : 100 - normalized[Math.min(activeIndex, normalized.length - 1)] * 100;

  function handleMove(event) {
    const bounds = event.currentTarget.getBoundingClientRect();
    const ratio = Math.min(Math.max((event.clientX - bounds.left) / Math.max(bounds.width, 1), 0), 1);
    onHoverIndex(Math.round(ratio * Math.max(values.length - 1, 0)));
  }

  return (
    <svg
      aria-hidden="true"
      className={`mini-chart ${accent}`}
      onMouseLeave={() => onHoverIndex(null)}
      onMouseMove={handleMove}
      preserveAspectRatio="none"
      viewBox="0 0 100 100"
    >
      <polyline fill="none" points={points} strokeWidth="3" />
      {markerX != null && markerY != null ? <circle cx={markerX} cy={markerY} r="3.2" /> : null}
    </svg>
  );
}

function MapPanel({ activeIndex, polyline }) {
  if (!polyline.length) {
    return <EmptyState compact text="No GPS points available." />;
  }
  const mapyApiKey = import.meta.env.VITE_MAPYCZ_API_KEY;
  const mapContainerRef = useRef(null);
  const mapStateRef = useRef(null);
  const [mapState, setMapState] = useState(mapyApiKey ? "loading" : "fallback");

  useEffect(() => {
    let cancelled = false;

    async function setupMap() {
      if (!mapyApiKey || !mapContainerRef.current) {
        setMapState("fallback");
        return;
      }

      const mapApi = await loadMapyCzApi();
      if (cancelled || !mapApi || !mapContainerRef.current) {
        setMapState("fallback");
        return;
      }

      const mapInstance = createMapyCzMap(mapApi, mapContainerRef.current, polyline);
      if (!mapInstance) {
        setMapState("fallback");
        return;
      }

      mapStateRef.current = mapInstance;
      setMapState("ready");
    }

    setupMap();

    return () => {
      cancelled = true;
      if (mapStateRef.current?.destroy) {
        mapStateRef.current.destroy();
      }
      mapStateRef.current = null;
    };
  }, [mapyApiKey, polyline]);

  useEffect(() => {
    if (mapState !== "ready" || !mapStateRef.current) {
      return;
    }
    mapStateRef.current.setActiveIndex(activeIndex);
  }, [activeIndex, mapState, polyline]);

  return (
    <div className="map-panel">
      <div className="map-header-note">
        {mapState === "ready"
          ? "Mapy.cz map active."
          : mapyApiKey
            ? "Mapy.cz tiles unavailable, route preview fallback active."
            : "Route preview fallback active."}
      </div>
      <div
        className={mapState === "fallback" || !mapyApiKey ? "mapycz-canvas hidden" : "mapycz-canvas"}
        ref={mapContainerRef}
      />
      {mapState !== "ready" ? (
        <>
          {mapyApiKey ? (
            <div className="map-loading-note">
              Mapy.cz background tiles could not be loaded. Check that the API key is valid, has Map Tiles access, and
              allows `http://localhost:5173`.
            </div>
          ) : null}
          <RoutePreview activeIndex={activeIndex} polyline={polyline} />
        </>
      ) : null}
    </div>
  );
}

function RoutePreview({ activeIndex, polyline }) {
  const latitudes = polyline.map((point) => point[0]);
  const longitudes = polyline.map((point) => point[1]);
  const minLat = Math.min(...latitudes);
  const maxLat = Math.max(...latitudes);
  const minLng = Math.min(...longitudes);
  const maxLng = Math.max(...longitudes);
  const coordinates = polyline.map(([lat, lng]) => ({
    x: ((lng - minLng) / Math.max(maxLng - minLng, 0.00001)) * 100,
    y: 100 - ((lat - minLat) / Math.max(maxLat - minLat, 0.00001)) * 100,
  }));
  const activePoint = activeIndex == null ? null : coordinates[Math.min(activeIndex, coordinates.length - 1)];
  return (
    <svg aria-hidden="true" className="route-map" preserveAspectRatio="none" viewBox="0 0 100 100">
      <polyline fill="none" points={coordinates.map(({ x, y }) => `${x},${y}`).join(" ")} strokeWidth="3" />
      <circle cx={coordinates[0].x} cy={coordinates[0].y} r="2.4" />
      {activePoint ? <circle className="active-route-point" cx={activePoint.x} cy={activePoint.y} r="3.2" /> : null}
    </svg>
  );
}

async function loadMapyCzApi() {
  const apiKey = import.meta.env.VITE_MAPYCZ_API_KEY;
  if (!apiKey) {
    return null;
  }

  const { default: L } = await import("leaflet");
  return {
    L,
    tileConfig: {
      attribution:
        '&copy; <a href="https://api.mapy.com/copyright" target="_blank" rel="noreferrer">Mapy.com</a>',
      maxZoom: 18,
      minZoom: 0,
      tileSize: 256,
      urlTemplate: `https://api.mapy.cz/v1/maptiles/outdoor/256/{z}/{x}/{y}?apikey=${apiKey}`,
    },
  };
}

function createMapyCzMap(mapApi, container, polyline) {
  if (!mapApi?.L || !mapApi?.tileConfig || !container || !polyline.length) {
    return null;
  }

  try {
    const { L, tileConfig } = mapApi;
    const coordinates = polyline.map(([lat, lng]) => [lat, lng]);
    const map = L.map(container, {
      attributionControl: false,
      zoomControl: true,
    });

    L.tileLayer(tileConfig.urlTemplate, {
      minZoom: tileConfig.minZoom,
      maxZoom: tileConfig.maxZoom,
      tileSize: tileConfig.tileSize,
      attribution: tileConfig.attribution,
    }).addTo(map);

    const route = L.polyline(coordinates, {
      color: "#fc4c02",
      weight: 4,
      opacity: 0.95,
    }).addTo(map);

    const activeMarker = L.circleMarker(coordinates[0], {
      color: "#1d7af3",
      fillColor: "#1d7af3",
      fillOpacity: 1,
      radius: 6,
      weight: 2,
    }).addTo(map);

    map.fitBounds(route.getBounds(), { padding: [24, 24] });

    const attribution = L.control.attribution({ prefix: false });
    attribution.addAttribution(tileConfig.attribution);
    attribution.addTo(map);

    requestAnimationFrame(() => {
      map.invalidateSize(false);
    });

    return {
      destroy() {
        map.remove();
      },
      setActiveIndex(activeIndex) {
        if (activeIndex == null) {
          activeMarker.setLatLng(coordinates[0]);
          return;
        }
        const nextPoint = coordinates[Math.min(activeIndex, coordinates.length - 1)];
        activeMarker.setLatLng(nextPoint);
        map.panTo(nextPoint, { animate: false });
      },
    };
  } catch {
    return null;
  }
}

function EmptyState({ compact = false, text }) {
  return <div className={compact ? "empty-state compact" : "empty-state"}>{text}</div>;
}

function AmbientBackdrop() {
  return (
    <div aria-hidden="true" className="ambient-backdrop">
      <div className="glow glow-one" />
      <div className="glow glow-two" />
      <div className="grid-haze" />
    </div>
  );
}

async function fetchJson(path, options = {}) {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
    ...options,
  });
  if (!response.ok) {
    const error = new Error(`Request failed with status ${response.status}`);
    error.status = response.status;
    throw error;
  }
  if (response.status === 204) {
    return null;
  }
  return response.json();
}

function buildQuery(params) {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value != null && value !== "") {
      searchParams.set(key, value);
    }
  });
  const query = searchParams.toString();
  return query ? `?${query}` : "";
}

function formatLabel(value) {
  return String(value)
    .replace(/_/g, " ")
    .replace(/-/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatMetricValue(value, suffix = "") {
  if (value == null) {
    return "n/a";
  }
  return `${formatNumber(value)}${suffix ? ` ${suffix}` : ""}`;
}

function formatDistanceMeters(value) {
  if (value == null) {
    return "n/a";
  }
  return `${formatNumber(Number(value) / 1000)} km`;
}

function formatNumber(value) {
  const numeric = Number(value);
  if (Number.isNaN(numeric)) {
    return String(value);
  }
  return numeric.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function formatDuration(totalSeconds) {
  if (totalSeconds == null) {
    return "n/a";
  }
  const seconds = Number(totalSeconds);
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainder = Math.floor(seconds % 60);
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
  }
  return `${minutes}:${String(remainder).padStart(2, "0")}`;
}

function formatPaceSeconds(value) {
  if (value == null) {
    return "n/a";
  }
  const numeric = Number(value);
  const minutes = Math.floor(numeric / 60);
  const seconds = Math.round(numeric % 60);
  return `${minutes}:${String(seconds).padStart(2, "0")} /km`;
}

function formatDateTime(value) {
  return new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function formatDateLabel(value) {
  return new Date(value).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function formatSyncProgress(syncStatus) {
  if (!syncStatus) {
    return "No sync recorded";
  }
  if (syncStatus.progress_total == null || syncStatus.progress_completed == null) {
    return "Progress unavailable";
  }
  return `${syncStatus.progress_completed} / ${syncStatus.progress_total}`;
}

function formatAny(value) {
  if (value == null) {
    return "n/a";
  }
  if (typeof value === "number") {
    return formatNumber(value);
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "object") {
    return Object.entries(value)
      .map(([key, nestedValue]) => `${formatLabel(key)}: ${formatAny(nestedValue)}`)
      .join(" | ");
  }
  return String(value);
}

function normalizeSeries(values) {
  const finiteValues = values.filter((value) => Number.isFinite(value));
  if (!finiteValues.length) {
    return values.map(() => 0);
  }
  const minValue = Math.min(...finiteValues);
  const maxValue = Math.max(...finiteValues);
  if (maxValue === minValue) {
    return values.map(() => 0.5);
  }
  return values.map((value) => (Number.isFinite(value) ? (value - minValue) / (maxValue - minValue) : 0));
}

function startOfMonth(value) {
  return new Date(value.getFullYear(), value.getMonth(), 1);
}

function shiftMonth(value, delta) {
  return new Date(value.getFullYear(), value.getMonth() + delta, 1);
}

function formatLocalDateKey(value) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function buildCalendarDays(calendarMonth, activities) {
  const firstDay = new Date(calendarMonth.getFullYear(), calendarMonth.getMonth(), 1);
  const firstGridDay = new Date(firstDay);
  const mondayOffset = (firstDay.getDay() + 6) % 7;
  firstGridDay.setDate(firstGridDay.getDate() - mondayOffset);
  const maxDailyDistance = activities.reduce((maxValue, activity) => {
    const distance = Number(activity.distance_km ?? 0);
    return Math.max(maxValue, distance);
  }, 0);

  return Array.from({ length: 42 }, (_, index) => {
    const date = new Date(firstGridDay);
    date.setDate(firstGridDay.getDate() + index);
    const localDay = formatLocalDateKey(date);
    const dayActivities = activities.filter(
      (activity) => (activity.start_date_local ?? "").slice(0, 10) === localDay,
    );
    return {
      date,
      isCurrentMonth: date.getMonth() === calendarMonth.getMonth(),
      activities: dayActivities,
      summary: buildCalendarSummary(dayActivities, maxDailyDistance),
    };
  });
}

function buildCalendarSummary(dayActivities, maxDailyDistance) {
  if (!dayActivities.length) {
    return null;
  }

  const distanceBySport = new Map();
  let totalDistanceKm = 0;
  let primaryActivityId = dayActivities[0].id;
  let primaryActivityDistance = Number(dayActivities[0].distance_km ?? 0);

  dayActivities.forEach((activity) => {
    const distanceKm = Number(activity.distance_km ?? 0);
    totalDistanceKm += distanceKm;
    distanceBySport.set(activity.sport_type, (distanceBySport.get(activity.sport_type) ?? 0) + distanceKm);
    if (distanceKm > primaryActivityDistance) {
      primaryActivityDistance = distanceKm;
      primaryActivityId = activity.id;
    }
  });

  const dominantSport = [...distanceBySport.entries()].sort((left, right) => right[1] - left[1])[0]?.[0] ?? "Run";
  const scale = maxDailyDistance > 0 ? totalDistanceKm / maxDailyDistance : 0;

  return {
    activityCount: dayActivities.length,
    colorClass: dominantSport === "Run" ? "is-run" : "is-ride",
    distanceKm: roundNumber(totalDistanceKm),
    dominantSport,
    primaryActivityId,
    sizePx: Math.round(26 + scale * 34),
  };
}

function roundNumber(value) {
  return Math.round(value * 10) / 10;
}
