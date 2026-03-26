import {startTransition, useEffect, useEffectEvent, useMemo, useRef, useState} from "react";
import "leaflet/dist/leaflet.css";

import {
    adminStravaAthleteId,
    defaultLandingCredentialState,
    syncPollIntervalMs,
    views,
} from "./constants";
import {AuthScreen, AmbientBackdrop, LoadingScreen, Sidebar, Toolbar} from "./components/common";
import {AdminView, ActivitiesView, BestEffortsView, CalendarView, DashboardView, SettingsView} from "./components/views";
import {fetchJson, generateRequestId} from "./utils/api";
import {
    buildComparisonPeriodOptions,
    buildQuery,
    isSyncInFlight,
    startOfMonth,
} from "./utils/data";
import {
    buildProfileFormFromItem,
    formatDateInput,
    parsePaceInput,
} from "./utils/formatters";

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
                isSetupModalOpen={setupModalOpen}
                landingCredentialState={landingCredentialState}
                onChangeAuthField={(field, value) => {
                    setAuthForm((current) => ({...current, [field]: value}));
                }}
                onCloseSetupModal={() => setSetupModalOpen(false)}
                onEditSavedCredentials={() => {
                    setAuthForm((current) => ({
                        ...current,
                        clientId: current.clientId || landingCredentialState.client_id || "",
                        clientSecret: "",
                        mode: "manual",
                    }));
                    setSetupModalOpen(true);
                }}
                onLogin={handleAuthPrimaryAction}
                onOpenSetupModal={() => setSetupModalOpen(true)}
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
                            profileBusy={profileBusy}
                            profileForm={profileForm}
                            syncBusy={syncBusy}
                            syncStatus={syncStatus}
                            user={user}
                            onChangeProfileField={(field, value) => {
                                setProfileForm((current) => ({...current, [field]: value}));
                            }}
                            onLogout={handleLogout}
                            onRefreshSync={handleRefreshSync}
                            onSaveProfile={handleSaveProfile}
                            onStartNewThresholdProfile={() => {
                                setProfileForm((current) => ({...current, effectiveFrom: ""}));
                            }}
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
