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
const adminStravaAthleteId = 102168741;
const windows = [
    {id: "week", label: "Week"},
    {id: "month", label: "Month"},
    {id: "year", label: "Year"},
];
const sports = [
    {id: "", label: "All Sports"},
    {id: "Run", label: "Run"},
    {id: "Ride", label: "Ride"},
    {id: "EBikeRide", label: "E-Bike"},
];
const syncPollIntervalMs = 3000;
const defaultLandingCredentialState = {
    client_id: "",
    has_saved_secret: false,
    can_connect: false,
    strava_api_settings_url: "https://www.strava.com/settings/api",
};
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
    const [profileHistory, setProfileHistory] = useState([]);
    const [adminUsers, setAdminUsers] = useState([]);
    const [adminBusy, setAdminBusy] = useState(false);
    const [adminActionUserId, setAdminActionUserId] = useState(null);
    const [landingCredentialState, setLandingCredentialState] = useState(defaultLandingCredentialState);
    const [authForm, setAuthForm] = useState({
        clientId: "",
        clientSecret: "",
        mode: "manual",
    });
    const [setupModalOpen, setSetupModalOpen] = useState(false);
    const profileSaveInFlightRef = useRef(false);
    const [profileForm, setProfileForm] = useState({
        effectiveFrom: formatDateInput(new Date()),
        aerobicThresholdHeartRate: "",
        anaerobicThresholdHeartRate: "",
        aerobicThresholdPace: "",
        anaerobicThresholdPace: "",
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
    const isAdmin = user?.strava_athlete_id === adminStravaAthleteId;
    const availableViews = isAdmin ? [...views, "admin"] : views;

    const transitionToAnonymous = useEffectEvent(async () => {
        await loadLandingCredentialState();
        setSessionState("anonymous");
        setUser(null);
        setSelectedView("dashboard");
        setSelectedActivityId(null);
        setActivityDetail(null);
        setActivityDetailState("idle");
        setAdminUsers([]);
        setErrorMessage("");
    });

    const pollSyncStatus = useEffectEvent(async () => {
        try {
            setSyncStatus(await fetchJson("/sync/status"));
        } catch (error) {
            if (error.status === 401) {
                await transitionToAnonymous();
            }
        }
    });

    const loadLandingCredentialState = useEffectEvent(async () => {
        try {
            const payload = await fetchJson("/auth/strava/credentials");
            setLandingCredentialState(payload);
            setAuthForm({
                clientId: payload.client_id ?? "",
                clientSecret: "",
                mode: payload.can_connect ? "saved" : "manual",
            });
        } catch (error) {
            setLandingCredentialState(defaultLandingCredentialState);
            setAuthForm({
                clientId: "",
                clientSecret: "",
                mode: "manual",
            });
            setErrorMessage(error.message ?? "Failed to load saved Strava app credentials.");
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
                    await loadLandingCredentialState();
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
                if (!active) {
                    return;
                }
                if (error.status === 401) {
                    await transitionToAnonymous();
                    return;
                }
                setErrorMessage(error.message ?? "Failed to load application data.");
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
        async function loadActivityDetail() {
            try {
                setActivityDetailState("loading");
                const payload = await fetchJson(`/activities/${selectedActivityId}`);
                if (!active) {
                    return;
                }
                setActivityDetail(payload);
                setActivityDetailState("ready");
            } catch (error) {
                if (!active) {
                    return;
                }
                if (error.status === 401) {
                    await transitionToAnonymous();
                    return;
                }
                setActivityDetailState("error");
                setErrorMessage(error.message ?? "Failed to load activity detail.");
            }
        }
        loadActivityDetail();
        return () => {
            active = false;
        };
    }, [selectedActivityId, sessionState]);

    useEffect(() => {
        if (sessionState !== "authenticated" || selectedView !== "settings") {
            return;
        }
        let active = true;
        const requestId = generateRequestId();
        async function loadProfile() {
            try {
                const payload = await fetchJson("/me/profile", {requestId, requestLabel: "load profile settings"});
                if (!active) {
                    return;
                }
                setProfileHistory(payload.items ?? []);
                setProfileForm(buildProfileFormFromItem(payload.current));
            } catch (error) {
                if (!active) {
                    return;
                }
                if (error.status === 401) {
                    await transitionToAnonymous();
                    return;
                }
                setErrorMessage(error.message ?? "Failed to load profile settings.");
            }
        }
        loadProfile();
        return () => {
            active = false;
        };
    }, [selectedView, sessionState]);

    useEffect(() => {
        if (sessionState !== "authenticated" || selectedView !== "admin" || !isAdmin) {
            return;
        }
        let active = true;
        async function loadAdminUsersView() {
            try {
                setAdminBusy(true);
                const payload = await fetchJson("/admin/users");
                if (!active) {
                    return;
                }
                setAdminUsers(payload.items ?? []);
                setErrorMessage("");
            } catch (error) {
                if (!active) {
                    return;
                }
                if (error.status === 401) {
                    await transitionToAnonymous();
                    return;
                }
                setErrorMessage(error.message ?? "Failed to load admin users.");
            } finally {
                if (active) {
                    setAdminBusy(false);
                }
            }
        }
        loadAdminUsersView();
        return () => {
            active = false;
        };
    }, [isAdmin, selectedView, sessionState]);

    useEffect(() => {
        if (selectedView === "admin" && !isAdmin) {
            setSelectedView("dashboard");
        }
    }, [isAdmin, selectedView]);

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
            const payload = await fetchJson("/auth/strava/login", {
                method: "POST",
                body: JSON.stringify(
                    authForm.mode === "saved"
                        ? {use_saved_credentials: true}
                        : {
                            client_id: authForm.clientId.trim(),
                            client_secret: authForm.clientSecret.trim(),
                            use_saved_credentials: false,
                        },
                ),
            });
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
            await loadLandingCredentialState();
            setSessionState("logged_out");
            setUser(null);
            setActivityDetail(null);
            setSelectedActivityId(null);
            setActivityDetailState("idle");
            setErrorMessage("");
        } catch (error) {
            setErrorMessage(error.message ?? "Failed to log out.");
        }
    }

    function hasManualCredentials() {
        return authForm.clientId.trim().length > 0 && authForm.clientSecret.trim().length > 0;
    }

    function handleAuthPrimaryAction() {
        if (authBusy) {
            return;
        }
        if (authForm.mode === "saved" ? landingCredentialState.can_connect : hasManualCredentials()) {
            handleLogin();
            return;
        }
        setSetupModalOpen(true);
    }

    function handleOpenSetupModal() {
        setSetupModalOpen(true);
    }

    function handleCloseSetupModal() {
        setSetupModalOpen(false);
    }

    function handleEditSavedCredentials() {
        setAuthForm((current) => ({
            ...current,
            clientId: current.clientId || landingCredentialState.client_id || "",
            clientSecret: "",
            mode: "manual",
        }));
        setSetupModalOpen(true);
    }

    async function handleRefreshSync() {
        try {
            setSyncBusy(true);
            await fetchJson("/sync/refresh", {method: "POST"});
            setSyncStatus(await fetchJson("/sync/status"));
            setErrorMessage("");
        } catch (error) {
            if (error.status === 401) {
                await transitionToAnonymous();
                return;
            }
            setErrorMessage(error.message ?? "Failed to trigger sync.");
        } finally {
            setSyncBusy(false);
        }
    }

    async function handleSaveProfile() {
        if (profileSaveInFlightRef.current) {
            return;
        }
        const requestId = generateRequestId();
        try {
            if (!profileForm.effectiveFrom) {
                setErrorMessage("Effective-from date is required.");
                return;
            }
            const parsedAetPace = parsePaceInput(profileForm.aerobicThresholdPace);
            const parsedAntPace = parsePaceInput(profileForm.anaerobicThresholdPace);
            if (profileForm.aerobicThresholdPace.trim() && parsedAetPace == null) {
                setErrorMessage("Aerobic threshold pace must use mm:ss or decimal minutes.");
                return;
            }
            if (profileForm.anaerobicThresholdPace.trim() && parsedAntPace == null) {
                setErrorMessage("Anaerobic threshold pace must use mm:ss or decimal minutes.");
                return;
            }
            profileSaveInFlightRef.current = true;
            setProfileBusy(true);
            const payload = await fetchJson("/me/profile", {
                method: "PUT",
                requestId,
                requestLabel: "save profile settings",
                body: JSON.stringify({
                    effective_from: profileForm.effectiveFrom,
                    aet_heart_rate_bpm: profileForm.aerobicThresholdHeartRate ? Number(profileForm.aerobicThresholdHeartRate) : null,
                    ant_heart_rate_bpm: profileForm.anaerobicThresholdHeartRate ? Number(profileForm.anaerobicThresholdHeartRate) : null,
                    aet_pace_min_per_km: profileForm.aerobicThresholdPace.trim() ? parsedAetPace : null,
                    ant_pace_min_per_km: profileForm.anaerobicThresholdPace.trim() ? parsedAntPace : null,
                }),
            });
            setProfileHistory(payload.items ?? []);
            setProfileForm(buildProfileFormFromItem(payload.current));
            setErrorMessage("");
        } catch (error) {
            if (error.status === 401) {
                await transitionToAnonymous();
                return;
            }
            setErrorMessage(error.message ?? "Failed to save profile settings.");
        } finally {
            profileSaveInFlightRef.current = false;
            setProfileBusy(false);
        }
    }

    async function handleDisableUser(userId) {
        try {
            setAdminActionUserId(userId);
            await fetchJson(`/admin/users/${userId}/disable`, {method: "POST"});
            setAdminUsers((current) => current.map((item) => (item.id === userId ? {...item, is_active: false} : item)));
            setErrorMessage("");
        } catch (error) {
            if (error.status === 401) {
                await transitionToAnonymous();
                return;
            }
            setErrorMessage(error.message ?? "Failed to disable user.");
        } finally {
            setAdminActionUserId(null);
        }
    }

    if (sessionState === "loading") {
        return <LoadingScreen/>;
    }

    if (sessionState === "anonymous" || sessionState === "logged_out") {
        return (
            <AuthScreen
                authBusy={authBusy}
                authForm={authForm}
                errorMessage={errorMessage}
                isLoggedOut={sessionState === "logged_out"}
                landingCredentialState={landingCredentialState}
                isSetupModalOpen={setupModalOpen}
                onChangeAuthField={(field, value) => {
                    setAuthForm((current) => ({...current, [field]: value}));
                }}
                onCloseSetupModal={handleCloseSetupModal}
                onEditSavedCredentials={handleEditSavedCredentials}
                onLogin={handleAuthPrimaryAction}
                onOpenSetupModal={handleOpenSetupModal}
            />
        );
    }

    return (
        <main className="app-shell">
            <AmbientBackdrop/>
            <div className="app-frame">
                <Sidebar
                    availableViews={availableViews}
                    selectedView={selectedView}
                    user={user}
                    onSelectView={setSelectedView}
                />
                <section className="workspace">
                    <Toolbar
                        calendarMonth={calendarMonth}
                        dateFrom={dateFrom}
                        dateTo={dateTo}
                        selectedSport={selectedSport}
                        selectedView={selectedView}
                        selectedWindow={selectedWindow}
                        onChangeCalendarMonth={setCalendarMonth}
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
                            profileHistory={profileHistory}
                            syncBusy={syncBusy}
                            profileBusy={profileBusy}
                            profileForm={profileForm}
                            syncStatus={syncStatus}
                            user={user}
                            onChangeProfileField={(field, value) => {
                                setProfileForm((current) => ({...current, [field]: value}));
                            }}
                            onStartNewThresholdProfile={() => {
                                setProfileForm((current) => ({...current, effectiveFrom: ""}));
                            }}
                            onLogout={handleLogout}
                            onRefreshSync={handleRefreshSync}
                            onSaveProfile={handleSaveProfile}
                        />
                    ) : null}
                    {selectedView === "admin" ? (
                        <AdminView
                            actionUserId={adminActionUserId}
                            adminUsers={adminUsers}
                            busy={adminBusy}
                            onDisableUser={handleDisableUser}
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

function AuthScreen({
                        authBusy,
                        authForm,
                        errorMessage,
                        isLoggedOut,
                        isSetupModalOpen,
                        landingCredentialState,
                        onChangeAuthField,
                        onCloseSetupModal,
                        onEditSavedCredentials,
                        onLogin,
                        onOpenSetupModal
                    }) {
    const hasSavedCredentials = authForm.mode === "saved" && landingCredentialState.can_connect;
    const hasManualCredentials = authForm.clientId.trim().length > 0 && authForm.clientSecret.trim().length > 0;
    const canConnect = hasSavedCredentials || hasManualCredentials;
    const primaryButtonLabel = authBusy ? "Opening Strava..." : "Login to Strava";
    const heroTitle = isLoggedOut ? "Back to your training archive." : "Your Strava history, kept simple.";
    const heroCopy = isLoggedOut
        ? "Your data is still here. Connect again and continue."
        : "Login once. Review everything locally.";
    const secondaryButtonLabel = "Set Strava credentials";
    const subCopy = hasSavedCredentials ? "Ready when you are." : "First time? Set up your app, then log in.";

    return (
        <main className="app-shell landing-shell">
            <AmbientBackdrop/>
            <section className="landing-panel auth-panel">
                <div className="landing-copy landing-copy-simple">
                    <p className="eyebrow">Strava Insights</p>
                    <h1>{heroTitle}</h1>
                    <p className="copy landing-copy-compact">{heroCopy}</p>
                    <p className="copy landing-subcopy">{hasManualCredentials ? "Ready for login." : subCopy}</p>
                    {errorMessage ? <p className="banner-error">{errorMessage}</p> : null}
                    <div className="landing-actions">
                        <button className="strava-connect-button is-primary" disabled={authBusy} onClick={onLogin} type="button">
                            <span className="strava-connect-mark" aria-hidden="true">
                                <span className="strava-connect-chevron tall"/>
                                <span className="strava-connect-chevron short"/>
                            </span>
                            <span>{primaryButtonLabel}</span>
                        </button>
                        <button className="ghost-button landing-setup-button" onClick={hasSavedCredentials ? onEditSavedCredentials : onOpenSetupModal} type="button">
                            {secondaryButtonLabel}
                        </button>
                    </div>
                </div>
                <div className="auth-brand-card landing-hero-card" aria-label="Strava compatibility notice">
                    <div className="auth-brand-lockup landing-brand-copy">
                        <div className="auth-brand-wordmark" aria-label="Strava">
                            <span className="strava-connect-chevron tall"/>
                            <span className="strava-connect-chevron short"/>
                            <span className="auth-brand-word">Strava</span>
                        </div>
                        <p className="auth-brand-mark">Compatible with Strava</p>
                        <p className="copy">Fast local dashboard. Less text. One clear login path.</p>
                        <p className="copy landing-legal-copy">
                            Separate app. Not developed or sponsored by Strava.
                        </p>
                    </div>
                </div>
            </section>
            {isSetupModalOpen ? (
                <div className="modal-backdrop" role="presentation">
                    <section aria-labelledby="setup-dialog-title" aria-modal="true" className="setup-modal" role="dialog">
                        <div className="setup-modal-header">
                            <div>
                                <p className="eyebrow">Strava App</p>
                                <h2 id="setup-dialog-title">Set up your Strava app</h2>
                                <p className="copy">Paste your client ID and secret, then return to login.</p>
                            </div>
                            <button aria-label="Close setup" className="ghost-button compact-inline-button" onClick={onCloseSetupModal} type="button">
                                Close
                            </button>
                        </div>
                        <div className="auth-credential-grid">
                            <label className="control-chip">
                                <span>Strava Client ID</span>
                                <input
                                    autoComplete="off"
                                    inputMode="numeric"
                                    type="text"
                                    value={authForm.clientId}
                                    onChange={(event) => onChangeAuthField("clientId", event.target.value)}
                                />
                            </label>
                            <label className="control-chip">
                                <span>Strava Client Secret</span>
                                <input
                                    autoComplete="off"
                                    type="password"
                                    value={authForm.clientSecret}
                                    onChange={(event) => onChangeAuthField("clientSecret", event.target.value)}
                                />
                            </label>
                        </div>
                        <div className="setup-modal-actions">
                            <button className="primary-button" onClick={onCloseSetupModal} type="button">
                                Save for next login
                            </button>
                            <button className="ghost-button" onClick={onLogin} type="button">
                                {canConnect ? "Save and login" : "Login after setup"}
                            </button>
                        </div>
                    </section>
                </div>
            ) : null}
        </main>
    );
}

function Sidebar({availableViews, selectedView, user, onSelectView}) {
    return (
        <aside className="sidebar">
            <div className="sidebar-user">
                <p className="eyebrow">Athlete</p>
                <h2 className="sidebar-title">{user.display_name}</h2>
            </div>
            <nav aria-label="Primary" className="sidebar-nav">
                {availableViews.map((view) => (
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
                     calendarMonth,
                     dateFrom,
                     dateTo,
                     selectedSport,
                     selectedView,
                     selectedWindow,
                     onChangeCalendarMonth,
                     onChangeDateFrom,
                     onChangeDateTo,
                     onSelectSport,
                     onSelectWindow,
                 }) {
    const showSportFilter = selectedView === "dashboard" || selectedView === "calendar" || selectedView === "activities" || selectedView === "best-efforts";
    const showWindowFilter = selectedView === "dashboard";
    const showDateFilters = selectedView === "activities";
    const showCalendarMonthFilter = selectedView === "calendar";

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
                {showCalendarMonthFilter ? (
                    <FilterMonth
                        label="Month"
                        value={calendarMonth}
                        onChange={onChangeCalendarMonth}
                    />
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

function FilterMonth({label, value, onChange}) {
    return (
        <label className="control-chip">
            <span>{label}</span>
            <input type="month" value={formatMonthInput(value)} onChange={(event) => onChange(parseMonthInput(event.target.value))}/>
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
                            <span className="activity-row-left">
                                <strong className="activity-row-name">{activity.name}</strong>
                                <span className="activity-row-date">{activity.start_date_local ? formatDateLabel(activity.start_date_local) : "Unknown date"}</span>
                            </span>
                            <span className="activity-row-right">
                                <strong className="activity-row-distance">{formatNumber(Number(activity.distance_km ?? 0))} km</strong>
                                <span className="activity-row-type">{formatSportLabel(activity.sport_type)}</span>
                            </span>
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
    const isRun = detail.sport_type === "Run";
    const isRide = detail.sport_type === "Ride" || detail.sport_type === "EBikeRide";
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
                    label={detail.kpis.summary_metric_kind === "speed" ? "Speed" : "Pace"}
                    value={formatSummaryMetricDisplay(detail.kpis.summary_metric_display, detail.kpis.summary_metric_kind)}
                />
                <MetricTile label="Elevation"
                            value={detail.kpis.total_elevation_gain_meters != null ? `${detail.kpis.total_elevation_gain_meters} m` : "n/a"}/>
                <MetricTile label="Average HR"
                            value={detail.kpis.average_heartrate_bpm != null ? `${detail.kpis.average_heartrate_bpm} bpm` : "n/a"}/>
                {isRide ? (
                    <MetricTile
                        label="Cadence"
                        value={detail.kpis.average_cadence != null ? `${formatNumber(detail.kpis.average_cadence)} rpm` : "n/a"}
                    />
                ) : null}
                <MetricTile label="HR Drift" value={formatHeartRateDrift(detail.kpis.heart_rate_drift_bpm)}/>
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
                    label={detail.series.pace_minutes_per_km.length ? "Pace" : "Speed"}
                    altitudeValues={detail.series.altitude_meters}
                    onSelectIndex={onSelectSeriesIndex}
                    referenceValue={paceReferenceValue}
                    thresholds={detail.thresholds}
                    valueKind={detail.series.pace_minutes_per_km.length ? "pace" : "speed"}
                    values={paceOrSpeed}
                />
                <DetailChart
                    accent="red"
                    activeIndex={resolvedActiveIndex}
                    distanceValues={detail.series.distance_km}
                    label="Heart Rate"
                    altitudeValues={detail.series.altitude_meters}
                    onSelectIndex={onSelectSeriesIndex}
                    referenceValue={heartRateReferenceValue}
                    thresholds={detail.thresholds}
                    valueKind="heart_rate"
                    values={detail.series.moving_average_heartrate}
                />
                <DetailChart
                    accent="green"
                    activeIndex={resolvedActiveIndex}
                    distanceValues={detail.series.distance_km}
                    label="Slope"
                    altitudeValues={detail.series.altitude_meters}
                    onSelectIndex={onSelectSeriesIndex}
                    referenceValue={slopeReferenceValue}
                    valueKind="slope"
                    values={detail.series.slope_percent}
                />
            </div>
            <div className="detail-analysis-grid">
                <div className="detail-card">
                    <p className="eyebrow">{isRide ? "Cycling Analysis" : "Running Analysis"}</p>
                    {isRun && detail.running_analysis ? (
                        <RunningAnalysisCard analysis={detail.running_analysis}/>
                    ) : null}
                    {isRun && !detail.running_analysis ? (
                        <EmptyState compact text="Add AeT and AnT pace and heart-rate thresholds in Settings to unlock running analysis."/>
                    ) : null}
                    {isRide && detail.cycling_analysis ? <CyclingAnalysisCard analysis={detail.cycling_analysis}/> : null}
                    {isRide && !detail.cycling_analysis ? (
                        <EmptyState compact text="Cycling analysis needs ride speed data. Add heart-rate thresholds in Settings to unlock HR-based ride intensity metrics."/>
                    ) : null}
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
                         onSelectIndex,
                         referenceValue,
                         thresholds,
                         valueKind
                     }) {
    return (
        <div className="detail-card">
            <p className="eyebrow">{label}</p>
            <MiniLineChart
                accent={accent}
                activeIndex={activeIndex}
                altitudeValues={altitudeValues}
                distanceValues={distanceValues}
                label={label}
                onSelectIndex={onSelectIndex}
                referenceValue={referenceValue}
                thresholds={thresholds}
                valueKind={valueKind}
                values={values}
            />
        </div>
    );
}

function RunningAnalysisCard({analysis}) {
    return (
        <div className="settings-list">
            <div className="settings-row">
                <MetricHelpLabel label="Pace Bands" tooltipKey="pace_bands"/>
                <strong>{formatBandDistribution(analysis.pace_distribution)}</strong>
            </div>
            <div className="settings-row">
                <MetricHelpLabel label="HR Bands" tooltipKey="hr_bands"/>
                <strong>{formatBandDistribution(analysis.heart_rate_distribution)}</strong>
            </div>
            <div className="settings-row">
                <MetricHelpLabel label="Agreement" tooltipKey="agreement"/>
                <strong>{formatPercentage(analysis.agreement.matching_share_percent)}</strong>
            </div>
            <div className="settings-row">
                <MetricHelpLabel label="Pace Above HR" tooltipKey="pace_above_hr"/>
                <strong>{formatPercentage(analysis.agreement.pace_higher_share_percent)}</strong>
            </div>
            <div className="settings-row">
                <MetricHelpLabel label="HR Above Pace" tooltipKey="hr_above_pace"/>
                <strong>{formatPercentage(analysis.agreement.heart_rate_higher_share_percent)}</strong>
            </div>
            <div className="settings-row">
                <MetricHelpLabel label="Longest AeT to AnT" tooltipKey="longest_aet_to_ant"/>
                <strong>{formatDistanceKm(analysis.steady_threshold_block.distance_km)}</strong>
            </div>
            <div className="settings-row">
                <MetricHelpLabel label="Longest Above AnT" tooltipKey="longest_above_ant"/>
                <strong>{formatDistanceKm(analysis.above_threshold_block.distance_km)}</strong>
            </div>
            <div className="settings-row">
                <span>Activity Evaluation</span>
                <span className="running-analysis-copy">{analysis.activity_evaluation}</span>
            </div>
            <div className="settings-row">
                <span>Further Training Suggestion</span>
                <span className="running-analysis-copy">{analysis.further_training_suggestion}</span>
            </div>
        </div>
    );
}

const RUNNING_ANALYSIS_TOOLTIPS = {
    pace_bands: "Shows how your running pace was distributed across Below AeT, AeT to AnT, and Above AnT bands during the activity.",
    hr_bands: "Shows how your heart rate was distributed across the same threshold bands, so you can compare internal effort with pace output.",
    agreement: "Measures how often pace intensity and heart-rate intensity landed in the same threshold band at the same point of the run.",
    pace_above_hr: "Highlights sections where pace looked harder than heart-rate response, which can happen early in a run or in favorable conditions.",
    hr_above_pace: "Highlights sections where heart rate looked harder than pace output, which can point to fatigue, heat, hills, or drift.",
    longest_aet_to_ant: "The longest continuous stretch where both pace and heart rate stayed in the AeT to AnT range, indicating steady threshold work.",
    longest_above_ant: "The longest continuous stretch where pace or heart rate stayed above AnT, showing your longest hard-intensity segment.",
};

const CYCLING_ANALYSIS_TOOLTIPS = {
    speed_bands: "Shows how ride distance was distributed across slower, steady, and faster-than-steady speed segments relative to your own session average.",
    hr_bands: "Shows how your heart rate was distributed across Below AeT, AeT to AnT, and Above AnT bands during the ride.",
    climbing_share: "Shows how much of the ride distance was spent climbing, flat, or descending based on the local slope profile.",
    longest_aerobic_block: "The longest continuous section where heart rate stayed below AeT, indicating your longest steady aerobic segment.",
    longest_above_ant: "The longest continuous section where heart rate stayed above AnT, indicating your longest hard cardiovascular segment.",
    average_cadence: "Shows the average pedaling cadence recorded for the ride in revolutions per minute.",
};

function CyclingAnalysisCard({analysis}) {
    return (
        <div className="settings-list">
            <div className="settings-row">
                <MetricHelpLabel label="Speed Bands" tooltipKey="speed_bands" tooltipMap={CYCLING_ANALYSIS_TOOLTIPS}/>
                <strong>{formatBandDistribution(analysis.speed_distribution)}</strong>
            </div>
            {analysis.heart_rate_distribution ? (
                <div className="settings-row">
                    <MetricHelpLabel label="HR Bands" tooltipKey="hr_bands" tooltipMap={CYCLING_ANALYSIS_TOOLTIPS}/>
                    <strong>{formatBandDistribution(analysis.heart_rate_distribution)}</strong>
                </div>
            ) : null}
            <div className="settings-row">
                <MetricHelpLabel label="Climbing Share" tooltipKey="climbing_share" tooltipMap={CYCLING_ANALYSIS_TOOLTIPS}/>
                <strong>{formatClimbingSummary(analysis.climbing_summary)}</strong>
            </div>
            {analysis.steady_aerobic_block ? (
                <div className="settings-row">
                    <MetricHelpLabel label="Longest Aerobic Block" tooltipKey="longest_aerobic_block" tooltipMap={CYCLING_ANALYSIS_TOOLTIPS}/>
                    <strong>{formatDistanceKm(analysis.steady_aerobic_block.distance_km)}</strong>
                </div>
            ) : null}
            {analysis.above_threshold_block ? (
                <div className="settings-row">
                    <MetricHelpLabel label="Longest Above AnT" tooltipKey="longest_above_ant" tooltipMap={CYCLING_ANALYSIS_TOOLTIPS}/>
                    <strong>{formatDistanceKm(analysis.above_threshold_block.distance_km)}</strong>
                </div>
            ) : null}
            <div className="settings-row">
                <MetricHelpLabel label="Average Cadence" tooltipKey="average_cadence" tooltipMap={CYCLING_ANALYSIS_TOOLTIPS}/>
                <strong>{analysis.average_cadence != null ? `${formatNumber(analysis.average_cadence)} rpm` : "n/a"}</strong>
            </div>
            <div className="settings-row">
                <span>Activity Evaluation</span>
                <span className="running-analysis-copy">{analysis.activity_evaluation}</span>
            </div>
            <div className="settings-row">
                <span>Further Training Suggestion</span>
                <span className="running-analysis-copy">{analysis.further_training_suggestion}</span>
            </div>
        </div>
    );
}

function MetricHelpLabel({label, tooltipKey, tooltipMap = RUNNING_ANALYSIS_TOOLTIPS}) {
    const [open, setOpen] = useState(false);
    const tooltipId = `tooltip-${tooltipKey}`;
    return (
        <span className="metric-help-label">
            <span>{label}</span>
            <button
                aria-describedby={open ? tooltipId : undefined}
                aria-label={`${label} explanation`}
                className="info-tooltip-trigger"
                onBlur={() => setOpen(false)}
                onFocus={() => setOpen(true)}
                onMouseEnter={() => setOpen(true)}
                onMouseLeave={() => setOpen(false)}
                type="button"
            >
                ?
            </button>
            {open ? (
                <span className="info-tooltip-panel" id={tooltipId} role="tooltip">
                    {tooltipMap[tooltipKey]}
                </span>
            ) : null}
        </span>
    );
}

function BestEffortsView({items, selectedSport, onSelectActivity}) {
    const heading = selectedSport === "Ride" || selectedSport === "EBikeRide"
        ? "Cycling marks"
        : selectedSport === "Run"
            ? "Running marks"
            : "All-sport marks";
    const groupedItems = groupBestEffortsBySport(items);
    return (
        <section className="panel">
            <div className="panel-header">
                <div>
                    <p className="eyebrow">Best Efforts</p>
                    <h2>{heading}</h2>
                </div>
            </div>
            {items.length === 0 ? <EmptyState text="No best efforts stored yet."/> : null}
            <div className="best-effort-groups">
                {groupedItems.map(([sportType, sportItems]) => (
                    <section key={sportType} className="best-effort-group">
                        <div className="best-effort-group-label">{formatSportLabel(sportType)}</div>
                        <div className="best-effort-row">
                            {sportItems.map((item) => (
                                <button
                                    key={`${item.sport_type}-${item.effort_code}`}
                                    className="best-effort-card"
                                    disabled={item.activity_id == null}
                                    onClick={() => onSelectActivity(item.activity_id)}
                                    type="button"
                                >
                                    <strong>{formatLabel(item.effort_code)}</strong>
                                    <span>{formatDuration(item.best_time_seconds)}</span>
                                    <p>{formatDistanceMeters(item.distance_meters)}</p>
                                    <small>{item.achieved_at ? formatDateLabel(item.achieved_at) : "Imported best mark"}</small>
                                </button>
                            ))}
                        </div>
                    </section>
                ))}
            </div>
        </section>
    );
}

function SettingsView({
                          profileHistory,
                          profileBusy,
                          profileForm,
                          syncBusy,
                          syncStatus,
                          user,
                          onChangeProfileField,
                          onStartNewThresholdProfile,
                          onLogout,
                          onRefreshSync,
                          onSaveProfile
                      }) {
    const latestThresholdProfile = profileHistory[0] ?? null;

    return (
        <section className="panel-grid">
            <article className="panel settings-panel panel-span-two">
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
                <div className="profile-account-actions">
                    <button className="ghost-button inline-button logout-button" onClick={onLogout} type="button">Log out</button>
                </div>
                <section className="settings-section">
                    <div className="settings-section-header">
                        <div>
                            <p className="eyebrow">Thresholds</p>
                            <h3>Current values</h3>
                        </div>
                    </div>
                    <p className="settings-helper-text">
                        Old periods stay in history automatically. This screen edits the current thresholds, or lets you create the next period from them.
                    </p>
                    <div className="profile-period-toolbar simple">
                        <div className={`threshold-selected-summary${!latestThresholdProfile || profileForm.effectiveFrom !== latestThresholdProfile.effective_from ? " is-draft" : ""}`}>
                            <strong>
                                {!latestThresholdProfile || profileForm.effectiveFrom !== latestThresholdProfile.effective_from
                                    ? "New period draft"
                                    : latestThresholdProfile?.effective_from ?? "No saved thresholds"}
                            </strong>
                            <span>
                                {!latestThresholdProfile || profileForm.effectiveFrom !== latestThresholdProfile.effective_from
                                    ? "Set a new effective date and save to create the next threshold period."
                                    : formatThresholdSnapshotSummary(latestThresholdProfile)}
                            </span>
                        </div>
                        <button className="ghost-button inline-button" onClick={onStartNewThresholdProfile} type="button">
                            Create New Period
                        </button>
                    </div>
                </section>
                <section className="settings-section">
                    <div className="settings-section-header">
                        <div>
                            <p className="eyebrow">Threshold Values</p>
                            <h3>Edit pace and heart rate</h3>
                        </div>
                    </div>
                    <p className="settings-helper-text">
                        Change the values below, then save them for the current effective date or as a new period.
                    </p>
                    <div className="threshold-form-grid">
                        <div className="threshold-metric-card threshold-date-card">
                            <p className="eyebrow">Effective Date</p>
                            <h4>When these thresholds begin</h4>
                            <label className="control-chip">
                                <span>Effective From</span>
                                <input
                                    aria-label="Effective From"
                                    type="date"
                                    value={profileForm.effectiveFrom}
                                    onChange={(event) => onChangeProfileField("effectiveFrom", event.target.value)}
                                />
                            </label>
                        </div>
                        <div className="threshold-metric-card">
                            <p className="eyebrow">Heart Rate</p>
                            <h4>Threshold bpm</h4>
                            <div className="threshold-input-grid">
                                <label className="control-chip">
                                    <span>Aerobic Threshold HR (bpm)</span>
                                    <input
                                        aria-label="Aerobic Threshold HR (bpm)"
                                        inputMode="numeric"
                                        step="1"
                                        type="number"
                                        value={profileForm.aerobicThresholdHeartRate}
                                        onChange={(event) => onChangeProfileField("aerobicThresholdHeartRate", event.target.value)}
                                    />
                                </label>
                                <label className="control-chip">
                                    <span>Anaerobic Threshold HR (bpm)</span>
                                    <input
                                        aria-label="Anaerobic Threshold HR (bpm)"
                                        inputMode="numeric"
                                        step="1"
                                        type="number"
                                        value={profileForm.anaerobicThresholdHeartRate}
                                        onChange={(event) => onChangeProfileField("anaerobicThresholdHeartRate", event.target.value)}
                                    />
                                </label>
                            </div>
                        </div>
                        <div className="threshold-metric-card">
                            <p className="eyebrow">Pace</p>
                            <h4>Threshold min/km</h4>
                            <div className="threshold-input-grid">
                                <label className="control-chip">
                                    <span>Aerobic Threshold Pace (min/km)</span>
                                    <input
                                        aria-label="Aerobic Threshold Pace (min/km)"
                                        inputMode="text"
                                        placeholder="5:20"
                                        type="text"
                                        value={profileForm.aerobicThresholdPace}
                                        onChange={(event) => onChangeProfileField("aerobicThresholdPace", event.target.value)}
                                    />
                                </label>
                                <label className="control-chip">
                                    <span>Anaerobic Threshold Pace (min/km)</span>
                                    <input
                                        aria-label="Anaerobic Threshold Pace (min/km)"
                                        inputMode="text"
                                        placeholder="4:15"
                                        type="text"
                                        value={profileForm.anaerobicThresholdPace}
                                        onChange={(event) => onChangeProfileField("anaerobicThresholdPace", event.target.value)}
                                    />
                                </label>
                            </div>
                        </div>
                    </div>
                    <div className="profile-actions">
                        <button className="primary-button" disabled={profileBusy} onClick={onSaveProfile} type="button">
                            {profileBusy ? "Saving..." : "Save Profile"}
                        </button>
                    </div>
                </section>
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

function AdminView({actionUserId, adminUsers, busy, onDisableUser}) {
    return (
        <section className="panel">
            <div className="panel-header">
                <div>
                    <p className="eyebrow">Admin</p>
                    <h2>Users</h2>
                </div>
            </div>
            {busy ? <EmptyState text="Loading users..."/> : null}
            {!busy && adminUsers.length === 0 ? <EmptyState text="No users found."/> : null}
            {!busy && adminUsers.length > 0 ? (
                <div aria-label="Users audit list" className="admin-user-list">
                    {adminUsers.map((item) => {
                        const isSelf = item.strava_athlete_id === adminStravaAthleteId;
                        const isDisabled = !item.is_active;
                        return (
                            <article key={item.id} className="admin-user-card">
                                <div className="admin-user-main">
                                    <div>
                                        <strong>{item.display_name}</strong>
                                        <p className="copy">Athlete {item.strava_athlete_id ?? "n/a"}</p>
                                    </div>
                                    <span className={isDisabled ? "status-pill is-disabled" : "status-pill is-active"}>
                                        {isDisabled ? "Disabled" : "Active"}
                                    </span>
                                </div>
                                <div className="admin-user-meta">
                                    <span>Last login</span>
                                    <strong>{item.last_login_at ? formatDateTime(item.last_login_at) : "Never"}</strong>
                                    <span>Created</span>
                                    <strong>{formatDateTime(item.created_at)}</strong>
                                </div>
                                <div className="admin-user-actions">
                                    {!isSelf ? (
                                        <button
                                            className="ghost-button"
                                            disabled={isDisabled || actionUserId === item.id}
                                            onClick={() => onDisableUser(item.id)}
                                            type="button"
                                        >
                                            {actionUserId === item.id ? "Rejecting..." : "Reject"}
                                        </button>
                                    ) : null}
                                </div>
                            </article>
                        );
                    })}
                </div>
            ) : null}
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
                <span className="trend-legend-item">
          <span className="trend-legend-swatch hr-drift"/>
          HR Drift
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
                        <YAxis
                            axisLine={false}
                            dataKey="hrDrift"
                            domain={["dataMin", "dataMax"]}
                            hide
                            orientation="right"
                            yAxisId="hrDrift"
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
                        <Line
                            connectNulls
                            dataKey="hrDrift"
                            dot={{fill: "#2f9e44", r: 4, stroke: "#ffffff", strokeWidth: 2}}
                            stroke="#2f9e44"
                            strokeWidth={2}
                            type="monotone"
                            yAxisId="hrDrift"
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
            {point.hrDrift != null ? <span>{formatHeartRateDrift(point.hrDrift)} hr drift</span> : null}
        </div>
    );
}

function DetailChartTooltip({active, label, payload, position, valueKind}) {
    const point = payload?.[0]?.payload;
    if (!active || !point) {
        return null;
    }
    return (
        <div
            className="detail-chart-tooltip"
            style={{
                left: `${position.leftPercent}%`,
                top: `${position.topPercent}%`,
                transform: position.preferBelow ? "translate(-50%, 12px)" : "translate(-50%, calc(-100% - 12px))",
            }}
        >
            <span>Distance: {formatNumber(point.distance)} km</span>
            <span>{label}: {formatTooltipSeriesValue(valueKind, point.value)}</span>
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
                           label,
                           onSelectIndex,
                           referenceValue,
                           thresholds,
                           valueKind,
                           values
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
    const numericAltitudes = useMemo(
        () => chartData.map((point) => point.altitude).filter(Number.isFinite),
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
    const thresholdGuides = useMemo(
        () => buildThresholdGuides({maxValue, minValue, thresholds, valueKind, xMax, xMin}),
        [maxValue, minValue, thresholds, valueKind, xMax, xMin],
    );
    const clampedActiveIndex = activeIndex == null ? null : Math.min(activeIndex, chartData.length - 1);
    const activePoint = useMemo(
        () => (clampedActiveIndex == null ? null : chartData[clampedActiveIndex]),
        [chartData, clampedActiveIndex],
    );
    const [isTooltipVisible, setIsTooltipVisible] = useState(false);
    const gradientId = `detail-elevation-${accent}-${valueKind}`;

    useEffect(() => {
        if (!activePoint || !Number.isFinite(activePoint.distance) || !Number.isFinite(activePoint.value)) {
            setIsTooltipVisible(false);
            return undefined;
        }
        setIsTooltipVisible(true);
        const timeoutId = window.setTimeout(() => {
            setIsTooltipVisible(false);
        }, 1600);
        return () => window.clearTimeout(timeoutId);
    }, [activePoint]);

    const tooltipPosition = useMemo(
        () => computeDetailTooltipPosition({
            activePoint,
            maxValue,
            minValue,
            valueKind,
            xMax,
            xMin,
        }),
        [activePoint, maxValue, minValue, valueKind, xMax, xMin],
    );

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
            {isTooltipVisible && activePoint && Number.isFinite(activePoint.distance) && Number.isFinite(activePoint.value) ? (
                <DetailChartTooltip
                    active
                    label={label}
                    payload={[{payload: activePoint}]}
                    position={tooltipPosition}
                    valueKind={valueKind}
                />
            ) : null}
            <ResponsiveContainer height="100%" width="100%">
                <ComposedChart
                    data={sampledChartData}
                    margin={{top: 10, right: 10, bottom: 16, left: 2}}
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
                        tickFormatter={(value) => formatAxisValue(valueKind, value)}
                        tickLine={false}
                        width={34}
                    />
                    <YAxis
                        axisLine={false}
                        dataKey="altitude"
                        domain={["dataMin", "dataMax"]}
                        hide={!numericAltitudes.length}
                        orientation="right"
                        tick={{fill: "rgba(100, 116, 139, 0.88)", fontSize: 10}}
                        tickFormatter={formatAltitudeAxisValue}
                        tickLine={false}
                        width={30}
                        yAxisId="altitude"
                    />
                    <Tooltip
                        content={() => null}
                        cursor={{stroke: "rgba(29, 122, 243, 0.28)", strokeDasharray: "4 4"}}
                    />
                    {thresholdGuides.bands.map((band) => (
                        <ReferenceArea
                            key={`threshold-band-${valueKind}-${band.code}`}
                            fill={band.color}
                            fillOpacity={0.1}
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
                    {thresholdGuides.lines.map((line) => (
                        <ReferenceLine
                            ifOverflow="extendDomain"
                            key={`threshold-line-${valueKind}-${line.label}`}
                            label={{fill: line.color, fontSize: 10, position: "insideTopRight", value: line.label}}
                            stroke={line.color}
                            strokeDasharray="3 4"
                            strokeWidth={1}
                            y={line.value}
                        />
                    ))}
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
    const {headers: optionHeaders, requestId = generateRequestId(), requestLabel = path, ...fetchOptions} = options;
    const url = `${apiBaseUrl}${path}`;
    const startedAt = performance.now();
    logFrontendRequest("info", {
        phase: "start",
        requestId,
        requestLabel,
        method: fetchOptions.method ?? "GET",
        url,
    });
    let response;
    try {
        response = await fetch(url, {
            credentials: "include",
            headers: {
                "Content-Type": "application/json",
                "X-Request-ID": requestId,
                ...(optionHeaders ?? {}),
            },
            ...fetchOptions,
        });
    } catch (cause) {
        const message = cause instanceof Error && cause.message ? cause.message : "Failed to fetch";
        logFrontendRequest("error", {
            phase: "network_error",
            requestId,
            requestLabel,
            method: fetchOptions.method ?? "GET",
            message,
            url,
        });
        const error = new Error(message);
        error.cause = cause;
        error.requestId = requestId;
        error.url = url;
        throw error;
    }
    const headerRequestId = response.headers?.get?.("x-request-id");
    const responseRequestId =
        typeof headerRequestId === "string" && headerRequestId.trim() && !headerRequestId.includes("/")
            ? headerRequestId
            : requestId;
    if (!response.ok) {
        let message = `Request failed with status ${response.status}`;
        const responseType = response.headers?.get?.("content-type") ?? "";
        if (responseType.includes("application/json")) {
            try {
                const payload = await response.json();
                if (typeof payload?.detail === "string" && payload.detail.trim()) {
                    message = payload.detail;
                }
            } catch {
                // Ignore malformed error bodies and keep the status-based message.
            }
        } else {
            try {
                const text = await response.text?.();
                if (typeof text === "string" && text.trim()) {
                    message = text.trim();
                }
            } catch {
                // Ignore unreadable text bodies and keep the status-based message.
            }
        }
        logFrontendRequest("error", {
            durationMs: Math.round(performance.now() - startedAt),
            phase: "http_error",
            requestId: responseRequestId,
            requestLabel,
            method: fetchOptions.method ?? "GET",
            status: response.status,
            url,
        });
        const error = new Error(message);
        error.status = response.status;
        error.requestId = responseRequestId;
        error.url = url;
        throw error;
    }
    if (response.status === 204) {
        logFrontendRequest("info", {
            durationMs: Math.round(performance.now() - startedAt),
            phase: "success",
            requestId: responseRequestId,
            requestLabel,
            method: fetchOptions.method ?? "GET",
            status: response.status,
            url,
        });
        return null;
    }
    const payload = await response.json();
    logFrontendRequest("info", {
        durationMs: Math.round(performance.now() - startedAt),
        phase: "success",
        requestId: responseRequestId,
        requestLabel,
        method: fetchOptions.method ?? "GET",
        status: response.status,
        url,
    });
    return payload;
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
    if (periodType === "week") {
        return `W${getWeekOfMonth(date)} ${date.toLocaleDateString(undefined, {month: "short", year: "numeric"})}`;
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
            hrDriftTotal: 0,
            hrDriftCount: 0,
        };
        current.distanceKm += Number(item.total_distance_meters ?? 0) / 1000;
        current.sessions += Number(item.activity_count ?? 0);
        if (item.average_heart_rate_drift_bpm != null) {
            current.hrDriftTotal += Number(item.average_heart_rate_drift_bpm);
            current.hrDriftCount += 1;
        }
        byDate.set(key, current);
    });
    return Array.from(byDate.values())
        .map((point) => ({
            ...point,
            hrDrift: point.hrDriftCount > 0 ? point.hrDriftTotal / point.hrDriftCount : null,
        }))
        .sort((left, right) => left.timestamp - right.timestamp);
}

function formatDateInput(value) {
    const date = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(date.getTime())) {
        return "";
    }
    return date.toISOString().slice(0, 10);
}

function formatMonthInput(value) {
    const date = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(date.getTime())) {
        return "";
    }
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    return `${year}-${month}`;
}

function parseMonthInput(value) {
    if (!value) {
        return startOfMonth(new Date());
    }
    const [yearText, monthText] = value.split("-");
    const year = Number(yearText);
    const monthIndex = Number(monthText) - 1;
    if (!Number.isInteger(year) || !Number.isInteger(monthIndex) || monthIndex < 0 || monthIndex > 11) {
        return startOfMonth(new Date());
    }
    return new Date(year, monthIndex, 1);
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

function getWeekOfMonth(value) {
    return Math.floor((value.getDate() - 1) / 7) + 1;
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

function formatTooltipSeriesValue(kind, value) {
    if (!Number.isFinite(value)) {
        return "n/a";
    }
    if (kind === "pace") {
        return `${formatPaceMinutes(value)} /km`;
    }
    return formatSeriesValue(kind, value);
}

export function formatAltitudeAxisValue(value) {
    if (!Number.isFinite(value)) {
        return "";
    }
    return `${Math.round(value)} m`;
}

export function formatAxisValue(kind, value) {
    if (!Number.isFinite(value)) {
        return "";
    }
    if (kind === "pace") {
        return formatPaceMinutes(value);
    }
    if (kind === "speed") {
        return formatNumber(value);
    }
    if (kind === "heart_rate") {
        return `${Math.round(value)}`;
    }
    if (kind === "slope") {
        return formatNumber(value);
    }
    return formatNumber(value);
}

function computeDetailTooltipPosition({activePoint, maxValue, minValue, valueKind, xMax, xMin}) {
    if (!activePoint || !Number.isFinite(activePoint.distance) || !Number.isFinite(activePoint.value)) {
        return {leftPercent: 50, preferBelow: false, topPercent: 18};
    }
    const xRange = xMax - xMin;
    const xRatio = xRange > 0 ? (activePoint.distance - xMin) / xRange : 0.5;
    const clampedXRatio = Math.min(Math.max(xRatio, 0.12), 0.88);

    const yRange = maxValue - minValue;
    const rawYRatio = yRange > 0 ? (activePoint.value - minValue) / yRange : 0.5;
    const normalizedYRatio = valueKind === "pace" ? rawYRatio : 1 - rawYRatio;
    const clampedYRatio = Math.min(Math.max(normalizedYRatio, 0.12), 0.82);
    const topPercent = 10 + (clampedYRatio * 74);

    return {
        leftPercent: 9 + (clampedXRatio * 82),
        preferBelow: topPercent < 22,
        topPercent,
    };
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

function formatHeartRateDrift(value) {
    if (value == null) {
        return "n/a";
    }
    const numericValue = Number(value);
    if (!Number.isFinite(numericValue)) {
        return "n/a";
    }
    const formatted = formatNumber(Math.abs(numericValue));
    const sign = numericValue > 0 ? "+" : numericValue < 0 ? "-" : "";
    return `${sign}${formatted} bpm`;
}

function formatPaceField(value) {
    const numericValue = Number(value);
    if (!Number.isFinite(numericValue) || numericValue <= 0) {
        return "";
    }
    return formatPaceMinutes(numericValue);
}

function parsePaceInput(value) {
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
        return Number(totalMinutes.toFixed(2));
    }
    const numericValue = Number(normalized);
    if (!Number.isFinite(numericValue) || numericValue <= 0) {
        return null;
    }
    return Number(numericValue.toFixed(2));
}

function buildProfileFormFromItem(item) {
    return {
        effectiveFrom: item?.effective_from ?? formatDateInput(new Date()),
        aerobicThresholdHeartRate: item?.aet_heart_rate_bpm == null ? "" : String(item.aet_heart_rate_bpm),
        anaerobicThresholdHeartRate: item?.ant_heart_rate_bpm == null ? "" : String(item.ant_heart_rate_bpm),
        aerobicThresholdPace: formatPaceField(item?.aet_pace_min_per_km),
        anaerobicThresholdPace: formatPaceField(item?.ant_pace_min_per_km),
    };
}

function formatThresholdSnapshotSummary(item) {
    if (!item) {
        return "No thresholds";
    }
    return [
        item.aet_heart_rate_bpm == null ? "AeT HR n/a" : `AeT HR ${item.aet_heart_rate_bpm}`,
        item.ant_heart_rate_bpm == null ? "AnT HR n/a" : `AnT HR ${item.ant_heart_rate_bpm}`,
        item.aet_pace_min_per_km == null ? "AeT pace n/a" : `AeT ${formatPaceField(item.aet_pace_min_per_km)}`,
        item.ant_pace_min_per_km == null ? "AnT pace n/a" : `AnT ${formatPaceField(item.ant_pace_min_per_km)}`,
    ].join(" | ");
}

function generateRequestId() {
    if (globalThis.crypto?.randomUUID) {
        return globalThis.crypto.randomUUID();
    }
    return `req-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
}

function logFrontendRequest(level, payload) {
    const logger = level === "error" ? console.error : console.info;
    logger("[api]", payload);
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

function groupBestEffortsBySport(items) {
    const sportOrder = new Map([
        ["Run", 0],
        ["Ride", 1],
        ["EBikeRide", 2],
    ]);
    const grouped = new Map();
    items.forEach((item) => {
        const current = grouped.get(item.sport_type) ?? [];
        current.push(item);
        grouped.set(item.sport_type, current);
    });
    return [...grouped.entries()].sort((left, right) => {
        const leftOrder = sportOrder.get(left[0]) ?? Number.MAX_SAFE_INTEGER;
        const rightOrder = sportOrder.get(right[0]) ?? Number.MAX_SAFE_INTEGER;
        if (leftOrder !== rightOrder) {
            return leftOrder - rightOrder;
        }
        return left[0].localeCompare(right[0]);
    });
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
        return 20;
    }

    if (dominantSport === "Run") {
        if (totalDistanceKm <= 10) {
            return 22;
        }
        if (totalDistanceKm <= 21.1) {
            return 32;
        }
        return 42;
    }

    const rideBucket = Math.min(Math.ceil(totalDistanceKm / 20), 8);
    return 19 + (rideBucket * 4);
}

function roundNumber(value) {
    return Math.round(value * 10) / 10;
}

export function buildThresholdGuides({maxValue, minValue, thresholds, valueKind, xMax, xMin}) {
    if (!thresholds || (valueKind !== "pace" && valueKind !== "heart_rate")) {
        return {bands: [], lines: []};
    }

    const rawAet = valueKind === "pace" ? Number(thresholds.aet_pace_min_per_km) : Number(thresholds.aet_heart_rate_bpm);
    const rawAnt = valueKind === "pace" ? Number(thresholds.ant_pace_min_per_km) : Number(thresholds.ant_heart_rate_bpm);
    if (!Number.isFinite(rawAet) || !Number.isFinite(rawAnt)) {
        return {bands: [], lines: []};
    }

    const aet = Math.max(minValue, Math.min(maxValue, rawAet));
    const ant = Math.max(minValue, Math.min(maxValue, rawAnt));
    const bandColors = {
        above_ant: "rgba(220, 38, 38, 0.18)",
        below_aet: "rgba(37, 99, 235, 0.16)",
        between_aet_ant: "rgba(245, 158, 11, 0.16)",
    };
    const lines = [
        {color: "rgba(37, 99, 235, 0.8)", label: "AeT", value: aet},
        {color: "rgba(220, 38, 38, 0.8)", label: "AnT", value: ant},
    ];

    if (valueKind === "pace") {
        return {
            bands: [
                {code: "above_ant", color: bandColors.above_ant, x1: xMin, x2: xMax, y1: minValue, y2: ant},
                {code: "between_aet_ant", color: bandColors.between_aet_ant, x1: xMin, x2: xMax, y1: ant, y2: aet},
                {code: "below_aet", color: bandColors.below_aet, x1: xMin, x2: xMax, y1: aet, y2: maxValue},
            ],
            lines,
        };
    }

    return {
        bands: [
            {code: "below_aet", color: bandColors.below_aet, x1: xMin, x2: xMax, y1: minValue, y2: aet},
            {code: "between_aet_ant", color: bandColors.between_aet_ant, x1: xMin, x2: xMax, y1: aet, y2: ant},
            {code: "above_ant", color: bandColors.above_ant, x1: xMin, x2: xMax, y1: ant, y2: maxValue},
        ],
        lines,
    };
}

function formatBandDistribution(items) {
    return (items ?? [])
        .map((item) => `${item.label} ${formatPercentage(item.share_percent)}`)
        .join(" | ");
}

function formatPercentage(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) {
        return "n/a";
    }
    return `${formatNumber(numeric)}%`;
}

function formatDistanceKm(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) {
        return "n/a";
    }
    return `${formatNumber(numeric)} km`;
}

function formatClimbingSummary(summary) {
    if (!summary) {
        return "n/a";
    }
    return `Climb ${formatPercentage(summary.climbing_share_percent)} | Flat ${formatPercentage(summary.flat_share_percent)} | Down ${formatPercentage(summary.descending_share_percent)}`;
}
