import {Fragment, startTransition, useEffect, useEffectEvent, useMemo, useRef, useState} from "react";
import "leaflet/dist/leaflet.css";
import {
  Area,
  Bar,
  Brush,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const views = ["dashboard", "calendar", "activities", "best-efforts", "settings"];
const windows = [
    {id: "week", label: "Week"},
    {id: "month", label: "Month"},
    {id: "year", label: "Year"},
    {id: "rolling_30d", label: "30 Days"},
];
const sports = [
    {id: "", label: "All Sports"},
    {id: "Run", label: "Run"},
    {id: "Ride", label: "Ride"},
    {id: "EBikeRide", label: "E-Bike"},
];
const syncPollIntervalMs = 3000;

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
    const [currentComparisonStart, setCurrentComparisonStart] = useState("");
    const [previousComparisonStart, setPreviousComparisonStart] = useState("");
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
    const [profileBusy, setProfileBusy] = useState(false);
    const [profileForm, setProfileForm] = useState({
        birthday: "",
        maxHeartRateOverride: "",
        maxPace: "",
    });

    const activityQuery = useMemo(
        () =>
            buildQuery({
                sport_type: selectedSport || undefined,
                date_from: dateFrom || undefined,
                date_to: dateTo || undefined,
            }),
        [dateFrom, dateTo, selectedSport],
    );

    const pollSyncStatus = useEffectEvent(async () => {
        try {
            setSyncStatus(await fetchJson("/sync/status"));
        } catch {
            // Keep the last known sync state if background polling fails.
        }
    });

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
                    fetchJson(`/dashboard${buildQuery({sport_type: selectedSport || undefined})}`),
                    fetchJson(`/activities${activityQuery}`),
                    fetchJson(`/best-efforts${buildQuery({sport_type: selectedSport || undefined})}`),
                    fetchJson(
                        `/comparisons${buildQuery({
                            period_type: selectedWindow,
                            current_period_start: selectedWindow === "rolling_30d" ? undefined : currentComparisonStart || undefined,
                            previous_period_start: selectedWindow === "rolling_30d" ? undefined : previousComparisonStart || undefined,
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
    }, [activityQuery, currentComparisonStart, previousComparisonStart, selectedSport, selectedWindow, sessionState]);

    useEffect(() => {
        if (selectedWindow === "rolling_30d") {
            if (currentComparisonStart !== "") {
                setCurrentComparisonStart("");
            }
            if (previousComparisonStart !== "") {
                setPreviousComparisonStart("");
            }
            return;
        }
        const options = buildComparisonPeriodOptions(trends?.items ?? [], selectedWindow);
        if (!options.length) {
            return;
        }
        const optionIds = new Set(options.map((option) => option.id));
        const nextCurrent = optionIds.has(currentComparisonStart) ? currentComparisonStart : options[0].id;
        const nextPrevious =
            optionIds.has(previousComparisonStart) && previousComparisonStart !== nextCurrent
                ? previousComparisonStart
                : options.find((option) => option.id !== nextCurrent)?.id ?? options[0].id;
        if (nextCurrent !== currentComparisonStart) {
            setCurrentComparisonStart(nextCurrent);
        }
        if (nextPrevious !== previousComparisonStart) {
            setPreviousComparisonStart(nextPrevious);
        }
    }, [currentComparisonStart, previousComparisonStart, selectedWindow, trends]);

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

    useEffect(() => {
        if (sessionState !== "authenticated" || selectedView !== "settings") {
            return;
        }
        let active = true;
        fetchJson("/me/profile")
            .then((payload) => {
                if (!active) {
                    return;
                }
                setProfileForm({
                    birthday: payload.birthday ?? "",
                    maxHeartRateOverride: payload.max_heart_rate_override == null ? "" : String(payload.max_heart_rate_override),
                    maxPace: formatSpeedMaxAsPace(payload.speed_max),
                });
            })
            .catch((error) => {
                if (active) {
                    setErrorMessage(error.message ?? "Failed to load profile settings.");
                }
            });
        return () => {
            active = false;
        };
    }, [selectedView, sessionState]);

    useEffect(() => {
        if (sessionState !== "authenticated" || !isSyncInFlight(syncStatus)) {
            return;
        }
        const intervalId = window.setInterval(() => {
            pollSyncStatus();
        }, syncPollIntervalMs);
        return () => {
            window.clearInterval(intervalId);
        };
    }, [pollSyncStatus, sessionState, syncStatus]);

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
            await fetchJson("/auth/logout", {method: "POST"});
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
            await fetchJson("/sync/refresh", {method: "POST"});
            setSyncStatus(await fetchJson("/sync/status"));
            setErrorMessage("");
        } catch (error) {
            setErrorMessage(error.message ?? "Failed to trigger sync.");
        } finally {
            setSyncBusy(false);
        }
    }

    async function handleSaveProfile() {
        try {
            const parsedSpeedMax = parsePaceToSpeedMax(profileForm.maxPace);
            if (profileForm.maxPace.trim() && parsedSpeedMax == null) {
                setErrorMessage("Max aerobic pace must use mm:ss or decimal minutes.");
                return;
            }
            setProfileBusy(true);
            const payload = await fetchJson("/me/profile", {
                method: "PUT",
                body: JSON.stringify({
                    birthday: profileForm.birthday || null,
                    max_heart_rate_override: profileForm.maxHeartRateOverride ? Number(profileForm.maxHeartRateOverride) : null,
                    speed_max: profileForm.maxPace.trim() ? parsedSpeedMax : null,
                }),
            });
            setProfileForm({
                birthday: payload.birthday ?? "",
                maxHeartRateOverride: payload.max_heart_rate_override == null ? "" : String(payload.max_heart_rate_override),
                maxPace: formatSpeedMaxAsPace(payload.speed_max),
            });
            setErrorMessage("");
        } catch (error) {
            setErrorMessage(error.message ?? "Failed to save profile settings.");
        } finally {
            setProfileBusy(false);
        }
    }

    if (sessionState === "loading") {
        return <LoadingScreen/>;
    }

    if (sessionState === "anonymous") {
        return <LandingScreen authBusy={authBusy} errorMessage={errorMessage} onLogin={handleLogin}/>;
    }

    return (
        <main className="app-shell">
            <AmbientBackdrop/>
            <div className="app-frame">
                <Sidebar
                    selectedView={selectedView}
                    user={user}
                    onSelectView={setSelectedView}
                />
                <section className="workspace">
                    <Toolbar
                        dateFrom={dateFrom}
                        dateTo={dateTo}
                        selectedSport={selectedSport}
                        selectedView={selectedView}
                        selectedWindow={selectedWindow}
                        onChangeDateFrom={setDateFrom}
                        onChangeDateTo={setDateTo}
                        onSelectSport={setSelectedSport}
                        onSelectWindow={setSelectedWindow}
                    />
                    {errorMessage ? <div className="banner-error">{errorMessage}</div> : null}
                    {selectedView === "dashboard" ? (
                        <DashboardView
                            comparisons={comparisons}
                            currentComparisonStart={currentComparisonStart}
                            dashboard={dashboard}
                            onChangeCurrentComparisonStart={setCurrentComparisonStart}
                            onChangePreviousComparisonStart={setPreviousComparisonStart}
                            previousComparisonStart={previousComparisonStart}
                            selectedWindow={selectedWindow}
                            trends={trends}
                        />
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
                            onSelectSeriesIndex={setActiveSeriesIndex}
                            onSelectActivity={setSelectedActivityId}
                        />
                    ) : null}
                    {selectedView === "best-efforts" ? (
                        <BestEffortsView
                            items={bestEfforts}
                            selectedSport={selectedSport}
                            onSelectActivity={(activityId) => {
                                if (activityId == null) {
                                    return;
                                }
                                setDateFrom("");
                                setDateTo("");
                                setSelectedActivityId(activityId);
                                setSelectedView("activities");
                            }}
                        />
                    ) : null}
                    {selectedView === "settings" ? (
                        <SettingsView
                            syncBusy={syncBusy}
                            profileBusy={profileBusy}
                            profileForm={profileForm}
                            syncStatus={syncStatus}
                            user={user}
                            onChangeProfileField={(field, value) => {
                                setProfileForm((current) => ({...current, [field]: value}));
                            }}
                            onLogout={handleLogout}
                            onRefreshSync={handleRefreshSync}
                            onSaveProfile={handleSaveProfile}
                        />
                    ) : null}
                </section>
            </div>
        </main>
    );
}

function LoadingScreen() {
    return (
        <main className="app-shell loading-state">
            <AmbientBackdrop/>
            <div className="loading-card">
                <p className="eyebrow">Strava Insights</p>
                <h1>Connecting to your local training archive.</h1>
                <p className="copy">Reading session and cached summaries.</p>
            </div>
        </main>
    );
}

function LandingScreen({authBusy, errorMessage, onLogin}) {
    return (
        <main className="app-shell landing-shell">
            <AmbientBackdrop/>
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
                    <MetricTile label="Comparison Windows" value="Week / Month / Year / 30d"/>
                    <MetricTile label="Read Model" value="Cached + DB-backed"/>
                    <MetricTile label="Activity Detail" value="Pace, slope, HR, zones"/>
                </div>
            </section>
        </main>
    );
}

function Sidebar({selectedView, user, onSelectView}) {
    return (
        <aside className="sidebar">
            <div className="sidebar-user">
                <p className="eyebrow">Athlete</p>
                <h2 className="sidebar-title">{user.display_name}</h2>
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
        </aside>
    );
}

function Toolbar({
                     dateFrom,
                     dateTo,
                     selectedSport,
                     selectedView,
                     selectedWindow,
                     onChangeDateFrom,
                     onChangeDateTo,
                     onSelectSport,
                     onSelectWindow,
                 }) {
    const showSportFilter = selectedView === "dashboard" || selectedView === "calendar" || selectedView === "activities" || selectedView === "best-efforts";
    const showWindowFilter = selectedView === "dashboard";
    const showDateFilters = selectedView === "activities";

    return (
        <header className="toolbar">
            <div>
                <p className="eyebrow">Review Surface</p>
                <h1 className="toolbar-title">{formatLabel(selectedView)}</h1>
            </div>
            <div className="toolbar-controls">
                {showSportFilter ? (
                    <FilterSelect label="Sport" options={sports} value={selectedSport} onChange={onSelectSport}/>
                ) : null}
                {showWindowFilter ? (
                    <FilterSelect label="Window" options={windows} value={selectedWindow} onChange={onSelectWindow}/>
                ) : null}
                {showDateFilters ? <FilterDate label="From" value={dateFrom} onChange={onChangeDateFrom}/> : null}
                {showDateFilters ? <FilterDate label="To" value={dateTo} onChange={onChangeDateTo}/> : null}
            </div>
        </header>
    );
}

function FilterSelect({label, options, value, onChange}) {
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

function FilterDate({label, value, onChange}) {
    return (
        <label className="control-chip">
            <span>{label}</span>
            <input type="date" value={value} onChange={(event) => onChange(event.target.value)}/>
        </label>
    );
}

function DashboardView({
                           comparisons,
                           currentComparisonStart,
                           dashboard,
                           onChangeCurrentComparisonStart,
                           onChangePreviousComparisonStart,
                           previousComparisonStart,
                           selectedWindow,
                           trends,
                       }) {
    const selectedComparisons = sortComparisons(comparisons);
    const comparisonOptions = buildComparisonPeriodOptions(trends?.items ?? [], selectedWindow);
    return (
        <section className="panel-grid">
            <article className="panel panel-span-full">
                <div className="panel-header">
                    <div>
                        <p className="eyebrow">Trend Series</p>
                        <h2>{trends ? formatLabel(trends.period_type) : "Rolling 30d"}</h2>
                    </div>
                </div>
                {trends ? <TrendList items={trends.items}/> :
                    <EmptyState text="Rolling 30-day mode compares windows directly."/>}
            </article>
            <article className="panel panel-span-full">
                <div className="panel-header">
                    <div>
                        <p className="eyebrow">Overview</p>
                    </div>
                </div>
                {selectedWindow !== "rolling_30d" && comparisonOptions.length > 1 ? (
                    <div className="comparison-period-controls">
                        <FilterSelect label="Current" options={comparisonOptions} value={currentComparisonStart}
                                      onChange={onChangeCurrentComparisonStart}/>
                        <FilterSelect label="Previous"
                                      options={comparisonOptions.filter((option) => option.id !== currentComparisonStart)}
                                      value={previousComparisonStart} onChange={onChangePreviousComparisonStart}/>
                    </div>
                ) : null}
                <div className="comparison-grid comparison-grid-overview">
                    {selectedComparisons.length === 0 ? <EmptyState text="No comparison data yet."/> : null}
                    {selectedComparisons.map((comparison, index) => (
                        <ComparisonCard
                            key={`${comparison.current?.sport_type ?? comparison.previous?.sport_type ?? "selected"}-${index}`}
                            comparison={comparison}
                        />
                    ))}
                </div>
            </article>
        </section>
    );
}

function CalendarView({activities, calendarMonth, onChangeMonth, onSelectActivity}) {
    const weeks = useMemo(() => buildCalendarWeeks(calendarMonth, activities), [activities, calendarMonth]);
    return (
        <section className="panel">
            <div className="panel-header">
                <div>
                    <p className="eyebrow">Calendar</p>
                    <h2>{calendarMonth.toLocaleDateString(undefined, {month: "long", year: "numeric"})}</h2>
                </div>
                <div className="calendar-controls">
                    <button className="ghost-button" onClick={() => onChangeMonth(shiftMonth(calendarMonth, -1))}
                            type="button">
                        Prev
                    </button>
                    <button className="ghost-button" onClick={() => onChangeMonth(shiftMonth(calendarMonth, 1))}
                            type="button">
                        Next
                    </button>
                </div>
            </div>
            <div className="calendar-grid">
                <div className="calendar-corner" aria-hidden="true"/>
                {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day) => (
                    <div className="calendar-head" key={day}>
                        {day}
                    </div>
                ))}
                {weeks.map((week) => (
                    <Fragment key={`week-${formatLocalDateKey(week.days[0].date)}`}>
                        <div className="calendar-week-label" aria-label={`Week ${week.weekNumber}`}>
                            {week.weekNumber}
                        </div>
                        {week.days.map((day) => (
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
                                            style={{"--bubble-size": `${day.summary.sizePx}px`}}
                                            type="button"
                                        >
                                            <span className="calendar-bubble-distance">{formatNumber(day.summary.distanceKm)}</span>
                                            <span className="calendar-bubble-unit">km</span>
                                        </button>
                                    ) : (
                                        <div className="calendar-bubble calendar-bubble-empty"/>
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
                    </Fragment>
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
                            onSelectSeriesIndex,
                            onSelectActivity,
                        }) {
    const selectedRowRef = useRef(null);

    useEffect(() => {
        if (!selectedRowRef.current || typeof selectedRowRef.current.scrollIntoView !== "function") {
            return;
        }
        selectedRowRef.current.scrollIntoView({block: "nearest"});
    }, [selectedActivityId, activities]);

    return (
        <section className="activities-layout">
            <article className="panel activity-list-panel">
                <div className="panel-header">
                    <div>
                        <p className="eyebrow">Activities</p>
                    </div>
                </div>
                <div className="activity-list">
                    {activities.length === 0 ? <EmptyState text="No activities imported yet."/> : null}
                    {activities.map((activity) => (
                        <button
                            key={activity.id}
                            className={selectedActivityId === activity.id ? "activity-row active" : "activity-row"}
                            onClick={() => onSelectActivity(activity.id)}
                            ref={selectedActivityId === activity.id ? selectedRowRef : null}
                            type="button"
                        >
                            <div>
                                <strong>{activity.name}</strong>
                                <p>{activity.sport_type}</p>
                            </div>
                            <div className="activity-row-kpis">
                                <span>{activity.distance_km ?? "?"} km</span>
                                <span>{formatSummaryMetricDisplay(activity.summary_metric_display, activity.summary_metric_kind)}</span>
                            </div>
                        </button>
                    ))}
                </div>
            </article>
            <article className="panel activity-detail-panel">
                {detailState === "idle" ? <EmptyState text="Select an activity to inspect the detail payload."/> : null}
                {detailState === "loading" ? <EmptyState text="Loading activity detail..."/> : null}
                {detailState === "error" ? <EmptyState text="Activity detail failed to load."/> : null}
                {detailState === "ready" && activityDetail ? (
                    <ActivityDetail detail={activityDetail} activeSeriesIndex={activeSeriesIndex}
                                    onSelectSeriesIndex={onSelectSeriesIndex}/>
                ) : null}
            </article>
        </section>
    );
}

function ActivityDetail({detail, activeSeriesIndex, onSelectSeriesIndex}) {
    const routePoints = detail.map?.polyline ?? [];
    const paceOrSpeed = detail.series.pace_minutes_per_km.length
        ? detail.series.pace_minutes_per_km
        : detail.series.moving_average_speed_kph;
    const paceReferenceValue = resolveDetailReferenceValue({
        averageValue: detail.kpis.summary_metric_display,
        summaryMetricKind: detail.kpis.summary_metric_kind ?? (detail.series.pace_minutes_per_km.length ? "pace" : "speed"),
        valueKind: detail.series.pace_minutes_per_km.length ? "pace" : "speed",
        values: paceOrSpeed,
    });
    const heartRateReferenceValue = resolveDetailReferenceValue({
        averageValue: detail.kpis.average_heartrate_bpm,
        valueKind: "heart_rate",
        values: detail.series.moving_average_heartrate,
    });
    const slopeReferenceValue = resolveDetailReferenceValue({
        valueKind: "slope",
        values: detail.series.slope_percent,
    });
    const resolvedActiveIndex = Math.min(activeSeriesIndex ?? 0, Math.max(routePoints.length - 1, 0));

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
                <MetricTile label="Distance"
                            value={detail.kpis.distance_km != null ? `${detail.kpis.distance_km} km` : "n/a"}/>
                <MetricTile label="Moving Time" value={detail.kpis.moving_time_display ?? "n/a"}/>
                <MetricTile
                    label="Pace"
                    value={formatSummaryMetricDisplay(detail.kpis.summary_metric_display, detail.kpis.summary_metric_kind)}
                />
                <MetricTile label="Elevation"
                            value={detail.kpis.total_elevation_gain_meters != null ? `${detail.kpis.total_elevation_gain_meters} m` : "n/a"}/>
                <MetricTile label="Average HR"
                            value={detail.kpis.average_heartrate_bpm != null ? `${detail.kpis.average_heartrate_bpm} bpm` : "n/a"}/>
            </div>
            <div className="detail-grid">
                <div className="detail-card detail-card-wide">
                    <p className="eyebrow">Route</p>
                    <MapPanel activeIndex={resolvedActiveIndex} onSelectIndex={onSelectSeriesIndex}
                              polyline={routePoints}/>
                </div>
                <DetailChart
                    accent="orange"
                    activeIndex={resolvedActiveIndex}
                    distanceValues={detail.series.distance_km}
                    label="Pace"
                    altitudeValues={detail.series.altitude_meters}
                    intervals={detail.intervals}
                    onSelectIndex={onSelectSeriesIndex}
                    referenceValue={paceReferenceValue}
                    valueKind={detail.series.pace_minutes_per_km.length ? "pace" : "speed"}
                    values={paceOrSpeed}
                    zones={detail.zones}
                />
                <DetailChart
                    accent="red"
                    activeIndex={resolvedActiveIndex}
                    distanceValues={detail.series.distance_km}
                    label="Heart Rate"
                    altitudeValues={detail.series.altitude_meters}
                    intervals={detail.intervals}
                    onSelectIndex={onSelectSeriesIndex}
                    referenceValue={heartRateReferenceValue}
                    valueKind="heart_rate"
                    values={detail.series.moving_average_heartrate}
                    zones={detail.zones}
                />
                <DetailChart
                    accent="green"
                    activeIndex={resolvedActiveIndex}
                    distanceValues={detail.series.distance_km}
                    label="Slope"
                    altitudeValues={detail.series.altitude_meters}
                    intervals={detail.intervals}
                    onSelectIndex={onSelectSeriesIndex}
                    referenceValue={slopeReferenceValue}
                    valueKind="slope"
                    values={detail.series.slope_percent}
                    zones={detail.zones}
                />
            </div>
            <div className="detail-analysis-grid">
                <div className="detail-card">
                    <p className="eyebrow">Running Analysis</p>
                    {detail.compliance ? (
                        <>
                            <strong>{detail.compliance.analysis_text ?? "Compliance summary available."}</strong>
                            <p className="sidebar-subtle">{detail.compliance.score_text ?? ""}</p>
                        </>
                    ) : (
                        <EmptyState compact text="No running compliance summary available for this activity."/>
                    )}
                </div>
            </div>
        </div>
    );
}

function DetailChart({
                         accent,
                         activeIndex,
                         label,
                         values,
                         distanceValues,
                         altitudeValues,
                         intervals,
                         onSelectIndex,
                         referenceValue,
                         valueKind,
                         zones
                     }) {
    return (
        <div className="detail-card">
            <p className="eyebrow">{label}</p>
            <MiniLineChart
                accent={accent}
                activeIndex={activeIndex}
                altitudeValues={altitudeValues}
                distanceValues={distanceValues}
                intervals={intervals}
                label={label}
                onSelectIndex={onSelectIndex}
                referenceValue={referenceValue}
                valueKind={valueKind}
                values={values}
                zones={zones}
            />
        </div>
    );
}

function BestEffortsView({items, selectedSport, onSelectActivity}) {
    const heading = selectedSport === "Ride" || selectedSport === "EBikeRide"
        ? "Cycling marks"
        : selectedSport === "Run"
            ? "Running marks"
            : "All-sport marks";
    return (
        <section className="panel">
            <div className="panel-header">
                <div>
                    <p className="eyebrow">Best Efforts</p>
                    <h2>{heading}</h2>
                </div>
            </div>
            <div className="best-effort-grid">
                {items.length === 0 ? <EmptyState text="No best efforts stored yet."/> : null}
                {items.map((item) => (
                    <button
                        key={item.effort_code}
                        className="best-effort-card"
                        disabled={item.activity_id == null}
                        onClick={() => onSelectActivity(item.activity_id)}
                        type="button"
                    >
                        <strong>{formatLabel(item.effort_code)}</strong>
                        <span>{formatDuration(item.best_time_seconds)}</span>
                        <p>{formatDistanceMeters(item.distance_meters)}</p>
                        <p className="sidebar-subtle">{formatSportLabel(item.sport_type)}</p>
                        <small>{item.achieved_at ? formatDateLabel(item.achieved_at) : "Imported best mark"}</small>
                    </button>
                ))}
            </div>
        </section>
    );
}

function SettingsView({
                          profileBusy,
                          profileForm,
                          syncBusy,
                          syncStatus,
                          user,
                          onChangeProfileField,
                          onLogout,
                          onRefreshSync,
                          onSaveProfile
                      }) {
    return (
        <section className="panel-grid">
            <article className="panel settings-panel">
                <div className="panel-header">
                    <div>
                        <p className="eyebrow">Profile</p>
                        <h2>{user.display_name}</h2>
                    </div>
                </div>
                <div className="settings-list">
                    <div className="settings-row"><span>Strava Athlete</span><strong>{user.strava_athlete_id}</strong>
                    </div>
                </div>
                <div className="settings-form">
                    <label className="control-chip">
                        <span>Birthday</span>
                        <input
                            aria-label="Birthday"
                            type="date"
                            value={profileForm.birthday}
                            onChange={(event) => onChangeProfileField("birthday", event.target.value)}
                        />
                    </label>
                    <label className="control-chip">
                        <span>Max Aerobic Pace (min/km)</span>
                        <input
                            aria-label="Max Aerobic Pace (min/km)"
                            inputMode="text"
                            placeholder="3:45"
                            type="text"
                            value={profileForm.maxPace}
                            onChange={(event) => onChangeProfileField("maxPace", event.target.value)}
                        />
                    </label>
                    <label className="control-chip">
                        <span>Max HR Override</span>
                        <input
                            aria-label="Max HR Override"
                            inputMode="numeric"
                            step="1"
                            type="number"
                            value={profileForm.maxHeartRateOverride}
                            onChange={(event) => onChangeProfileField("maxHeartRateOverride", event.target.value)}
                        />
                    </label>
                </div>
                <button className="primary-button" disabled={profileBusy} onClick={onSaveProfile} type="button">
                    {profileBusy ? "Saving..." : "Save Profile"}
                </button>
                <button className="ghost-button inline-button" onClick={onLogout} type="button">Log out</button>
            </article>
            <article className="panel settings-panel">
                <div className="panel-header">
                    <div>
                        <p className="eyebrow">Sync Status</p>
                        <h2>{formatLabel(syncStatus?.status ?? "idle")}</h2>
                    </div>
                </div>
                <div className="settings-list">
                    <div className="settings-row"><span>Type</span><strong>{syncStatus?.sync_type ?? "n/a"}</strong>
                    </div>
                    <div className="settings-row"><span>Progress</span><strong>{formatSyncProgress(syncStatus)}</strong>
                    </div>
                    <div className="settings-row">
                        <span>Started</span><strong>{syncStatus?.started_at ? formatDateTime(syncStatus.started_at) : "n/a"}</strong>
                    </div>
                    <div className="settings-row">
                        <span>Finished</span><strong>{syncStatus?.finished_at ? formatDateTime(syncStatus.finished_at) : "n/a"}</strong>
                    </div>
                </div>
                <button className="ghost-button" disabled={syncBusy} onClick={onRefreshSync} type="button">
                    {syncBusy ? "Refreshing..." : "Refresh Sync"}
                </button>
            </article>
        </section>
    );
}

function ComparisonCard({comparison}) {
    const current = comparison.current;
    const previous = comparison.previous;
    const isPace = current?.average_pace_seconds_per_km != null || previous?.average_pace_seconds_per_km != null;
    const periodType = current?.period_type ?? previous?.period_type ?? "period";
    return (
        <div className="comparison-card">
            <div className="comparison-heading">
                <strong>{current?.sport_type ?? previous?.sport_type ?? "Unknown"}</strong>
                <span
                    className="comparison-period-label">{formatComparisonRange(current?.period_start, previous?.period_start, periodType)}</span>
            </div>
            <MetricRow label="Distance" current={current?.total_distance_meters}
                       previous={previous?.total_distance_meters} renderValue={formatDistanceMeters}/>
            <MetricRow label="Moving Time" current={current?.total_moving_time_seconds}
                       previous={previous?.total_moving_time_seconds} renderValue={formatDuration}/>
            <MetricRow label="Activity Count" current={current?.activity_count} previous={previous?.activity_count}/>
            <MetricRow
                label={isPace ? "Average Pace" : "Average Speed"}
                current={current?.average_pace_seconds_per_km ?? current?.average_speed_mps}
                previous={previous?.average_pace_seconds_per_km ?? previous?.average_speed_mps}
                renderValue={isPace ? formatPaceSeconds : (value) => formatMetricValue(value, "m/s")}
            />
        </div>
    );
}

function TrendList({items}) {
    if (!items.length) {
        return <EmptyState text="No trend points yet."/>;
    }
    const points = aggregateTrendItems(items);
    const [activeIndex, setActiveIndex] = useState(points.length - 1);
    const periodType = items[0]?.period_type ?? "month";
    const chartData = points.map((point) => ({
        ...point,
        axisLabel: formatTrendAxisLabel(point.periodStart, periodType),
    }));

    return (
        <div className="trend-chart-shell">
            <div className="trend-chart-legend" aria-hidden="true">
        <span className="trend-legend-item">
          <span className="trend-legend-swatch distance"/>
          Km
        </span>
                <span className="trend-legend-item">
          <span className="trend-legend-swatch sessions"/>
          Sessions
        </span>
            </div>
            <div aria-label="Trend graph" className="trend-chart" role="img">
                <ResponsiveContainer height="100%" width="100%">
                    <ComposedChart
                        data={chartData}
                        margin={{top: 8, right: 12, bottom: 8, left: 0}}
                        onClick={(state) => {
                            if (Number.isInteger(state?.activeTooltipIndex)) {
                                setActiveIndex(state.activeTooltipIndex);
                            }
                        }}
                        onMouseMove={(state) => {
                            if (Number.isInteger(state?.activeTooltipIndex)) {
                                setActiveIndex(state.activeTooltipIndex);
                            }
                        }}
                    >
                        <CartesianGrid stroke="rgba(31, 41, 55, 0.10)" strokeDasharray="3 4" vertical={false}/>
                        <XAxis axisLine={false} dataKey="axisLabel" tick={{fill: "#6f6b62", fontSize: 11}}
                               tickLine={false}/>
                        <YAxis
                            axisLine={false}
                            domain={[0, "dataMax"]}
                            tick={{fill: "#6f6b62", fontSize: 11}}
                            tickFormatter={(value) => `${Math.round(value)}`}
                            tickLine={false}
                            width={28}
                        />
                        <YAxis
                            axisLine={false}
                            dataKey="sessions"
                            domain={[0, "dataMax"]}
                            hide
                            orientation="right"
                            yAxisId="sessions"
                        />
                        <Tooltip content={<TrendChartTooltip/>} cursor={{fill: "rgba(252, 76, 2, 0.08)"}}/>
                        <Bar dataKey="distanceKm" fill="#fc4c02" maxBarSize={42} radius={[10, 10, 4, 4]}/>
                        <Line
                            dataKey="sessions"
                            dot={{fill: "#1d7af3", r: 4, stroke: "#ffffff", strokeWidth: 2}}
                            stroke="#1d7af3"
                            strokeWidth={2}
                            type="monotone"
                            yAxisId="sessions"
                        />
                        <Brush
                            dataKey="axisLabel"
                            defaultEndIndex={points.length - 1}
                            defaultStartIndex={Math.max(points.length - 12, 0)}
                            fill="rgba(252, 76, 2, 0.08)"
                            height={22}
                            stroke="#fc4c02"
                            travellerWidth={12}
                        />
                    </ComposedChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}

function TrendChartTooltip({active, payload}) {
    const point = payload?.[0]?.payload;
    if (!active || !point) {
        return null;
    }
    return (
        <div className="trend-tooltip">
            <strong>{formatDateLabel(point.periodStart)}</strong>
            <span>{formatNumber(point.distanceKm)} km</span>
            <span>{point.sessions} sessions</span>
        </div>
    );
}

function MetricTile({label, value}) {
    return (
        <div className="metric-tile">
            <span>{label}</span>
            <strong>{value}</strong>
        </div>
    );
}

function MetricRow({label, current, previous, renderValue = formatMetricValue}) {
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

function MiniLineChart({
                           accent,
                           activeIndex,
                           altitudeValues,
                           distanceValues,
                           intervals,
                           label,
                           onSelectIndex,
                           referenceValue,
                           valueKind,
                           values,
                           zones
                       }) {
    if (!values?.length) {
        return <EmptyState compact text="No series available."/>;
    }
    const chartData = useMemo(() => {
        const seriesLength = values.length;
        const xValues =
            distanceValues?.length === seriesLength
                ? distanceValues.map((value) => Number(value ?? 0))
                : values.map((_, index) => index);
        const altitudeSeries =
            altitudeValues?.length === seriesLength
                ? altitudeValues.map((value) => Number(value ?? 0))
                : altitudeValues?.length
                    ? altitudeValues.slice(0, seriesLength).map((value) => Number(value ?? 0))
                    : [];
        return values.map((value, index) => ({
            altitude: Number.isFinite(Number(altitudeSeries[index])) ? Number(altitudeSeries[index]) : null,
            distance: Number.isFinite(Number(xValues[index])) ? Number(xValues[index]) : index,
            sourceIndex: index,
            value: Number.isFinite(Number(value)) ? Number(value) : null,
        }));
    }, [altitudeValues, distanceValues, values]);
    const sampledChartData = useMemo(() => downsampleChartData(chartData, activeIndex), [activeIndex, chartData]);
    const numericValues = useMemo(
        () => chartData.map((point) => point.value).filter(Number.isFinite),
        [chartData],
    );
    const numericDistances = useMemo(
        () => chartData.map((point) => point.distance).filter(Number.isFinite),
        [chartData],
    );
    const lineColor = getDetailAccentColor(accent);
    const referenceLineColor = getDetailReferenceColor(accent);

    if (!numericValues.length || !numericDistances.length) {
        return <EmptyState compact text="No series available."/>;
    }

    const {max: maxValue, min: minValue} = useMemo(() => {
        if (valueKind === "slope") {
            return expandChartDomain(Math.min(...numericValues, 0), Math.max(...numericValues, 0));
        }
        return expandChartDomain(Math.min(...numericValues), Math.max(...numericValues));
    }, [numericValues, valueKind]);
    const {xMax, xMin} = useMemo(
        () => ({
            xMax: Math.max(...numericDistances),
            xMin: Math.min(...numericDistances),
        }),
        [numericDistances],
    );
    const intervalBands = useMemo(
        () => buildIntervalBands({intervals, xMax, xMin, zones}),
        [intervals, xMax, xMin, zones],
    );
    const thresholdBands = useMemo(
        () => buildThresholdBands({maxValue, minValue, valueKind, xMax, xMin, zones}),
        [maxValue, minValue, valueKind, xMax, xMin, zones],
    );
    const clampedActiveIndex = activeIndex == null ? null : Math.min(activeIndex, chartData.length - 1);
    const activePoint = useMemo(
        () => (clampedActiveIndex == null ? null : chartData[clampedActiveIndex]),
        [chartData, clampedActiveIndex],
    );
    const gradientId = `detail-elevation-${accent}-${valueKind}`;

    function handleChartSelection(state) {
        const activeDistance = Number(state?.activeLabel);
        if (!Number.isFinite(activeDistance)) {
            return;
        }
        const nextIndex = findClosestDistanceIndex(chartData, activeDistance);
        if (Number.isInteger(nextIndex) && nextIndex >= 0) {
            onSelectIndex(nextIndex);
        }
    }

    return (
        <div aria-label={`${labelForValueKind(valueKind)} chart`} className={`mini-chart ${accent}`} role="img">
            <ResponsiveContainer height="100%" width="100%">
                <ComposedChart
                    data={sampledChartData}
                    margin={{top: 10, right: 12, bottom: 16, left: 8}}
                    onClick={handleChartSelection}
                    onMouseMove={handleChartSelection}
                    syncId="activity-detail-series"
                >
                    <defs>
                        <linearGradient id={gradientId} x1="0" x2="0" y1="0" y2="1">
                            <stop offset="0%" stopColor="rgba(100, 116, 139, 0.35)"/>
                            <stop offset="100%" stopColor="rgba(100, 116, 139, 0.08)"/>
                        </linearGradient>
                    </defs>
                    <CartesianGrid stroke="rgba(31, 41, 55, 0.10)" strokeDasharray="3 4" vertical={false}/>
                    <XAxis
                        axisLine={false}
                        dataKey="distance"
                        domain={[xMin, xMax]}
                        tick={{fill: "#6f6b62", fontSize: 11}}
                        tickFormatter={(value) => Math.round(value)}
                        tickLine={false}
                        type="number"
                    />
                    <YAxis
                        axisLine={false}
                        domain={[minValue, maxValue]}
                        reversed={valueKind === "pace"}
                        tick={{fill: "#6f6b62", fontSize: 11}}
                        tickFormatter={(value) => formatSeriesValue(valueKind, value)}
                        tickLine={false}
                        width={52}
                    />
                    <YAxis dataKey="altitude" domain={["dataMin", "dataMax"]} hide yAxisId="altitude"/>
                    <Tooltip
                        content={() => null}
                        cursor={{stroke: "rgba(29, 122, 243, 0.28)", strokeDasharray: "4 4"}}
                    />
                    {intervalBands.map((band, index) => (
                        <ReferenceArea
                            key={`interval-band-${index}`}
                            fill={band.color}
                            fillOpacity={0.12}
                            ifOverflow="extendDomain"
                            x1={band.x1}
                            x2={band.x2}
                            y1={minValue}
                            y2={maxValue}
                        />
                    ))}
                    {thresholdBands.map((band, index) => (
                        <ReferenceArea
                            key={`threshold-band-${index}`}
                            fill={band.color}
                            fillOpacity={0.16}
                            ifOverflow="extendDomain"
                            x1={xMin}
                            x2={xMax}
                            y1={band.y1}
                            y2={band.y2}
                        />
                    ))}
                    <Area
                        dataKey="altitude"
                        fill={`url(#${gradientId})`}
                        isAnimationActive={false}
                        stroke="rgba(100, 116, 139, 0.28)"
                        strokeWidth={1}
                        type="monotone"
                        yAxisId="altitude"
                    />
                    <Line
                        activeDot={false}
                        connectNulls
                        dataKey="value"
                        dot={false}
                        isAnimationActive={false}
                        stroke={lineColor}
                        strokeWidth={2.25}
                        type="monotone"
                    />
                    {Number.isFinite(referenceValue) ? (
                        <ReferenceLine
                            ifOverflow="extendDomain"
                            stroke={referenceLineColor}
                            strokeDasharray="5 5"
                            strokeWidth={1.5}
                            y={referenceValue}
                        />
                    ) : null}
                    {activePoint && Number.isFinite(activePoint.distance) ? (
                        <ReferenceLine stroke="rgba(29, 122, 243, 0.32)" strokeDasharray="4 4"
                                       x={activePoint.distance}/>
                    ) : null}
                    {activePoint && Number.isFinite(activePoint.distance) && Number.isFinite(activePoint.value) ? (
                        <ReferenceDot fill="#ffffff" r={4} stroke={lineColor} strokeWidth={2} x={activePoint.distance}
                                      y={activePoint.value}/>
                    ) : null}
                </ComposedChart>
            </ResponsiveContainer>
        </div>
    );
}

function MapPanel({activeIndex, onSelectIndex, polyline}) {
    if (!polyline.length) {
        return <EmptyState compact text="No GPS points available."/>;
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

            const mapInstance = createMapyCzMap(mapApi, mapContainerRef.current, polyline, onSelectIndex);
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
    }, [mapyApiKey, onSelectIndex, polyline]);

    useEffect(() => {
        if (mapState !== "ready" || !mapStateRef.current) {
            return;
        }
        mapStateRef.current.setActiveIndex(activeIndex);
    }, [activeIndex, mapState, polyline]);

    return (
        <div className="map-panel">
            {mapState !== "ready" ? (
                <div className="map-header-note">
                    {mapyApiKey
                        ? "Mapy.cz tiles unavailable, route preview fallback active."
                        : "Route preview fallback active."}
                </div>
            ) : null}
            <div
                className={mapState === "fallback" || !mapyApiKey ? "mapycz-canvas hidden" : "mapycz-canvas"}
                ref={mapContainerRef}
            />
            {mapState !== "ready" ? (
                <>
                    {mapyApiKey ? (
                        <div className="map-loading-note">
                            Mapy.cz background tiles could not be loaded. Check that the API key is valid, has Map Tiles
                            access, and
                            allows `http://localhost:5173`.
                        </div>
                    ) : null}
                    <RoutePreview activeIndex={activeIndex} onSelectIndex={onSelectIndex} polyline={polyline}/>
                </>
            ) : null}
        </div>
    );
}

function RoutePreview({activeIndex, onSelectIndex, polyline}) {
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

    function handlePointer(event) {
        const bounds = event.currentTarget.getBoundingClientRect();
        const x = ((event.clientX - bounds.left) / Math.max(bounds.width, 1)) * 100;
        const y = ((event.clientY - bounds.top) / Math.max(bounds.height, 1)) * 100;
        onSelectIndex(findClosestPointIndex(coordinates, {x, y}));
    }

    return (
        <svg
            aria-label="Route preview"
            className="route-map"
            onClick={handlePointer}
            preserveAspectRatio="none"
            viewBox="0 0 100 100"
        >
            <polyline fill="none" points={coordinates.map(({x, y}) => `${x},${y}`).join(" ")} strokeWidth="2"/>
            <circle cx={coordinates[0].x} cy={coordinates[0].y} r="2.4"/>
            {activePoint ?
                <circle className="active-route-point" cx={activePoint.x} cy={activePoint.y} r="3.2"/> : null}
        </svg>
    );
}

async function loadMapyCzApi() {
    const apiKey = import.meta.env.VITE_MAPYCZ_API_KEY;
    if (!apiKey) {
        return null;
    }

    const {default: L} = await import("leaflet");
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

function createMapyCzMap(mapApi, container, polyline, onSelectIndex) {
    if (!mapApi?.L || !mapApi?.tileConfig || !container || !polyline.length) {
        return null;
    }

    try {
        const {L, tileConfig} = mapApi;
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
            weight: 3,
            opacity: 0.95,
        }).addTo(map);

        const activeMarker = L.circleMarker(coordinates[0], {
            color: "#1d7af3",
            fillColor: "#1d7af3",
            fillOpacity: 1,
            radius: 6,
            weight: 2,
        }).addTo(map);

        map.fitBounds(route.getBounds(), {padding: [24, 24]});

        const attribution = L.control.attribution({prefix: false});
        attribution.addAttribution(tileConfig.attribution);
        attribution.addTo(map);

        requestAnimationFrame(() => {
            map.invalidateSize(false);
        });

        function updateSelection(latlng) {
            onSelectIndex(findClosestPointIndex(coordinates, {x: latlng.lat, y: latlng.lng}, "latlng"));
        }

        route.on("click", (event) => updateSelection(event.latlng));
        map.on("click", (event) => updateSelection(event.latlng));

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
            },
        };
    } catch {
        return null;
    }
}

function EmptyState({compact = false, text}) {
    return <div className={compact ? "empty-state compact" : "empty-state"}>{text}</div>;
}

function AmbientBackdrop() {
    return (
        <div aria-hidden="true" className="ambient-backdrop">
            <div className="glow glow-one"/>
            <div className="glow glow-two"/>
            <div className="grid-haze"/>
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
    return numeric.toLocaleString(undefined, {maximumFractionDigits: 2});
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
    return new Date(value).toLocaleString(undefined, {dateStyle: "medium", timeStyle: "short"});
}

function formatDateLabel(value) {
    return new Date(value).toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
    });
}

function formatTrendAxisLabel(value, periodType) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return String(value);
    }
    if (periodType === "year") {
        return date.toLocaleDateString(undefined, {year: "numeric"});
    }
    if (periodType === "week") {
        return `${getIsoWeek(date)}/${date.getFullYear()}`;
    }
    return date.toLocaleDateString(undefined, {month: "2-digit", year: "numeric"});
}

function formatComparisonRange(currentValue, previousValue, periodType) {
    const currentLabel = formatComparisonPeriod(currentValue, periodType);
    const previousLabel = formatComparisonPeriod(previousValue, periodType);
    if (currentLabel && previousLabel) {
        return `${currentLabel} vs ${previousLabel}`;
    }
    return currentLabel || previousLabel || "Period unavailable";
}

function formatComparisonPeriod(value, periodType) {
    if (!value) {
        return "";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return String(value);
    }
    if (periodType === "year") {
        return date.toLocaleDateString(undefined, {year: "numeric"});
    }
    return date.toLocaleDateString(undefined, {month: "2-digit", year: "numeric"});
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

function isSyncInFlight(syncStatus) {
    return syncStatus?.status === "queued" || syncStatus?.status === "running";
}

function aggregateTrendItems(items) {
    const byDate = new Map();
    items.forEach((item) => {
        const key = item.period_start;
        const current = byDate.get(key) ?? {
            periodStart: key,
            timestamp: new Date(key).getTime(),
            distanceKm: 0,
            sessions: 0,
        };
        current.distanceKm += Number(item.total_distance_meters ?? 0) / 1000;
        current.sessions += Number(item.activity_count ?? 0);
        byDate.set(key, current);
    });
    return Array.from(byDate.values()).sort((left, right) => left.timestamp - right.timestamp);
}

function buildComparisonPeriodOptions(items, periodType) {
    const uniqueStarts = Array.from(new Set(items.map((item) => item.period_start))).sort((left, right) => right.localeCompare(left));
    return uniqueStarts.map((value) => ({
        id: value,
        label: formatComparisonPeriod(value, periodType),
    }));
}

function sortComparisons(items) {
    return [...items].sort((left, right) => compareSportPriority(left.current?.sport_type ?? left.previous?.sport_type, right.current?.sport_type ?? right.previous?.sport_type));
}

function compareSportPriority(left, right) {
    const order = ["Run", "Ride", "EBikeRide"];
    const leftIndex = order.indexOf(left ?? "");
    const rightIndex = order.indexOf(right ?? "");
    const normalizedLeft = leftIndex === -1 ? Number.MAX_SAFE_INTEGER : leftIndex;
    const normalizedRight = rightIndex === -1 ? Number.MAX_SAFE_INTEGER : rightIndex;
    if (normalizedLeft !== normalizedRight) {
        return normalizedLeft - normalizedRight;
    }
    return String(left ?? "").localeCompare(String(right ?? ""));
}

function getIsoWeek(value) {
    const date = new Date(Date.UTC(value.getFullYear(), value.getMonth(), value.getDate()));
    const day = date.getUTCDay() || 7;
    date.setUTCDate(date.getUTCDate() + 4 - day);
    const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
    return Math.ceil((((date - yearStart) / 86400000) + 1) / 7);
}


function formatDistanceTick(value) {
    return `${Math.round(value)} km`;
}

function formatSeriesValue(kind, value) {
    if (!Number.isFinite(value)) {
        return "n/a";
    }
    if (kind === "pace") {
        return formatPaceMinutes(value);
    }
    if (kind === "speed") {
        return `${formatNumber(value)} km/h`;
    }
    if (kind === "heart_rate") {
        return `${Math.round(value)} bpm`;
    }
    if (kind === "slope") {
        return `${formatNumber(value)}%`;
    }
    return formatNumber(value);
}

function formatPaceMinutes(value) {
  const wholeMinutes = Math.floor(value);
  const seconds = Math.round((value - wholeMinutes) * 60);
  const normalizedMinutes = seconds === 60 ? wholeMinutes + 1 : wholeMinutes;
  const normalizedSeconds = seconds === 60 ? 0 : seconds;
  return `${normalizedMinutes}:${String(normalizedSeconds).padStart(2, "0")}`;
}

function formatSummaryMetricDisplay(value, kind) {
  if (!value) {
    return "n/a";
  }
  if (kind === "pace") {
    return `${value} min/km`;
  }
  if (kind === "speed") {
    return `${value} km/h`;
  }
  return value;
}

function formatSpeedMaxAsPace(value) {
  const numericValue = Number(value);
    if (!Number.isFinite(numericValue) || numericValue <= 0) {
        return "";
    }
    return formatPaceMinutes(60 / numericValue);
}

function parsePaceToSpeedMax(value) {
    if (!value?.trim()) {
        return null;
    }
    const normalized = value.trim().replace(",", ".");
    if (normalized.includes(":")) {
        const [minutesText, secondsText = "0"] = normalized.split(":");
        const minutes = Number(minutesText);
        const seconds = Number(secondsText);
        if (!Number.isFinite(minutes) || !Number.isFinite(seconds) || minutes < 0 || seconds < 0 || seconds >= 60) {
            return null;
        }
        const totalMinutes = minutes + (seconds / 60);
        if (totalMinutes <= 0) {
            return null;
        }
        return Number((60 / totalMinutes).toFixed(2));
    }
    const numericValue = Number(normalized);
    if (!Number.isFinite(numericValue) || numericValue <= 0) {
        return null;
    }
    return Number((60 / numericValue).toFixed(2));
}

function labelForValueKind(kind) {
    if (kind === "pace") {
        return "min/km";
    }
    if (kind === "speed") {
        return "km/h";
    }
    if (kind === "heart_rate") {
        return "bpm";
    }
    if (kind === "slope") {
        return "%";
    }
    return "value";
}

function findClosestPointIndex(points, target, mode = "xy") {
    let closestIndex = 0;
    let closestDistance = Number.POSITIVE_INFINITY;
    points.forEach((point, index) => {
        const dx = mode === "latlng" ? point[0] - target.x : point.x - target.x;
        const dy = mode === "latlng" ? point[1] - target.y : point.y - target.y;
        const distance = (dx * dx) + (dy * dy);
        if (distance < closestDistance) {
            closestDistance = distance;
            closestIndex = index;
        }
    });
    return closestIndex;
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

    return Array.from({length: 42}, (_, index) => {
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
            summary: buildCalendarSummary(dayActivities),
        };
    });
}

function formatSportLabel(value) {
    if (value === "EBikeRide") {
        return "E-Bike";
    }
    return formatLabel(value);
}

function buildCalendarWeeks(calendarMonth, activities) {
    const days = buildCalendarDays(calendarMonth, activities);
    return Array.from({length: days.length / 7}, (_, index) => {
        const weekDays = days.slice(index * 7, (index + 1) * 7);
        return {
            days: weekDays,
            weekNumber: getIsoWeek(weekDays[0].date),
        };
    });
}

function buildCalendarSummary(dayActivities) {
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

    return {
        activityCount: dayActivities.length,
        colorClass: dominantSport === "Run" ? "is-run" : "is-ride",
        distanceKm: roundNumber(totalDistanceKm),
        dominantSport,
        primaryActivityId,
        sizePx: scaleCalendarBubbleSize(totalDistanceKm, dominantSport),
    };
}

function buildIntervalBands({intervals, xMax, xMin, zones}) {
    if (!intervals?.length || !zones?.length) {
        return [];
    }
    const zoneColorMap = new Map(zones.map((zone) => [zone.name, zone.color]));
    return intervals
        .map((interval) => {
            const distances = interval.distance_km ?? [];
            if (!distances.length) {
                return null;
            }
            const start = Math.min(...distances);
            const end = Math.max(...distances, start + 0.05);
            const color = zoneColorMap.get(interval.zones?.zone_pace) ?? "#cfd5db";
            return {
                color,
                x1: Math.max(start, xMin),
                x2: Math.max(Math.min(end, xMax), start + 0.02),
            };
        })
        .filter(Boolean);
}

function buildThresholdBands({maxValue, minValue, valueKind, xMax, xMin, zones}) {
    if (!zones?.length || (valueKind !== "pace" && valueKind !== "heart_rate")) {
        return [];
    }
    const metricKey = valueKind === "pace" ? "range_zone_pace" : "range_zone_bpm";
    const usableZones = zones.filter((zone) => zone?.[metricKey] != null);
    if (!usableZones.length) {
        return [];
    }
    return usableZones
        .map((zone) => {
            const lower = Number(zone[metricKey].lower);
            const upper = Number(zone[metricKey].upper);
            if (!Number.isFinite(lower) || !Number.isFinite(upper)) {
                return null;
            }
            const clampedLower = Math.max(minValue, Math.min(maxValue, lower));
            const clampedUpper = Math.max(minValue, Math.min(maxValue, upper));
            return {
                color: zone.color,
                x1: xMin,
                x2: xMax,
                y1: clampedLower,
                y2: clampedUpper,
            };
        })
        .filter(Boolean);
}

function expandChartDomain(minValue, maxValue) {
    if (minValue === maxValue) {
        const padding = minValue === 0 ? 1 : Math.abs(minValue) * 0.08;
        return {max: maxValue + padding, min: minValue - padding};
    }
    const padding = (maxValue - minValue) * 0.08;
    return {
        max: maxValue + padding,
        min: minValue - padding,
    };
}

function getDetailAccentColor(accent) {
    if (accent === "red") {
        return "#d94841";
    }
    if (accent === "green") {
        return "#3d9b63";
    }
    return "#fc4c02";
}

function getDetailReferenceColor(accent) {
    if (accent === "red") {
        return "rgba(217, 72, 65, 0.42)";
    }
    if (accent === "green") {
        return "rgba(61, 155, 99, 0.42)";
    }
    return "rgba(252, 76, 2, 0.42)";
}

export function resolveDetailReferenceValue({averageValue, summaryMetricKind, valueKind, values}) {
    if (valueKind === "slope") {
        return 0;
    }
    if (valueKind === "heart_rate") {
        const numericAverage = averageValue == null ? Number.NaN : Number(averageValue);
        return Number.isFinite(numericAverage) ? numericAverage : averageSeriesValue(values);
    }
    if (valueKind === "pace" || valueKind === "speed") {
        const parsedAverage = parseSummaryMetricAverage(averageValue, summaryMetricKind ?? valueKind);
        return Number.isFinite(parsedAverage) ? parsedAverage : averageSeriesValue(values);
    }
    return averageSeriesValue(values);
}

export function parseSummaryMetricAverage(value, kind) {
    if (value == null) {
        return null;
    }
    const rawValue = String(value).trim();
    if (!rawValue) {
        return null;
    }
    if (kind === "speed") {
        const match = rawValue.match(/-?\d+(?:[.,]\d+)?/);
        if (!match) {
            return null;
        }
        const numeric = Number(match[0].replace(",", "."));
        return Number.isFinite(numeric) ? numeric : null;
    }
    if (kind === "pace") {
        const clockMatch = rawValue.match(/(\d+):(\d{1,2})/);
        if (clockMatch) {
            const minutes = Number(clockMatch[1]);
            const seconds = Number(clockMatch[2]);
            if (Number.isFinite(minutes) && Number.isFinite(seconds) && seconds >= 0 && seconds < 60) {
                return minutes + (seconds / 60);
            }
        }
        const numeric = Number(rawValue.replace(",", "."));
        return Number.isFinite(numeric) ? numeric : null;
    }
    return null;
}

function averageSeriesValue(values) {
    const numericValues = (values ?? []).map((value) => Number(value)).filter(Number.isFinite);
    if (!numericValues.length) {
        return null;
    }
    return numericValues.reduce((sum, value) => sum + value, 0) / numericValues.length;
}

function downsampleChartData(points, focusIndex, maxPoints = 240) {
    if (!points.length || points.length <= maxPoints) {
        return points;
    }
    const clampedFocusIndex = focusIndex == null ? null : Math.min(Math.max(focusIndex, 0), points.length - 1);
    const targetIndexes = new Set([0, points.length - 1]);
    if (clampedFocusIndex != null) {
        targetIndexes.add(clampedFocusIndex);
    }
    const step = (points.length - 1) / (maxPoints - 1);
    for (let index = 0; index < maxPoints; index += 1) {
        targetIndexes.add(Math.round(index * step));
    }
    return [...targetIndexes]
        .sort((left, right) => left - right)
        .map((index) => points[index]);
}

function findClosestDistanceIndex(points, targetDistance) {
    let closestIndex = -1;
    let closestDistance = Number.POSITIVE_INFINITY;
    points.forEach((point, index) => {
        const delta = Math.abs(Number(point.distance ?? 0) - targetDistance);
        if (delta < closestDistance) {
            closestDistance = delta;
            closestIndex = index;
        }
    });
    return closestIndex;
}

function scaleCalendarBubbleSize(totalDistanceKm, dominantSport) {
    if (totalDistanceKm <= 0) {
        return 28;
    }

    if (dominantSport === "Run") {
        if (totalDistanceKm <= 10) {
            return 32;
        }
        if (totalDistanceKm <= 21.1) {
            return 46;
        }
        return 60;
    }

    const rideBucket = Math.min(Math.ceil(totalDistanceKm / 20), 8);
    return 28 + (rideBucket * 5);
}

function roundNumber(value) {
    return Math.round(value * 10) / 10;
}
