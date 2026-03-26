import {sports, windows} from "../constants";
import {parseMonthInput} from "../utils/data";
import {formatLabel, formatMonthInput} from "../utils/formatters";

export function LoadingScreen() {
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

export function AuthScreen({
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
    onOpenSetupModal,
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

export function Sidebar({availableViews, selectedView, user, onSelectView}) {
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

export function Toolbar({
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
                {showSportFilter ? <FilterSelect label="Sport" options={sports} value={selectedSport} onChange={onSelectSport}/> : null}
                {showCalendarMonthFilter ? <FilterMonth label="Month" value={calendarMonth} onChange={onChangeCalendarMonth}/> : null}
                {showWindowFilter ? <FilterSelect label="Window" options={windows} value={selectedWindow} onChange={onSelectWindow}/> : null}
                {showDateFilters ? <FilterDate label="From" value={dateFrom} onChange={onChangeDateFrom}/> : null}
                {showDateFilters ? <FilterDate label="To" value={dateTo} onChange={onChangeDateTo}/> : null}
            </div>
        </header>
    );
}

export function FilterSelect({label, options, value, onChange}) {
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

export function FilterDate({label, value, onChange}) {
    return (
        <label className="control-chip">
            <span>{label}</span>
            <input type="date" value={value} onChange={(event) => onChange(event.target.value)}/>
        </label>
    );
}

export function FilterMonth({label, value, onChange}) {
    return (
        <label className="control-chip">
            <span>{label}</span>
            <input type="month" value={formatMonthInput(value)} onChange={(event) => onChange(parseMonthInput(event.target.value))}/>
        </label>
    );
}

export function EmptyState({compact = false, text}) {
    return <div className={compact ? "empty-state compact" : "empty-state"}>{text}</div>;
}

export function AmbientBackdrop() {
    return (
        <div aria-hidden="true" className="ambient-backdrop">
            <div className="glow glow-one"/>
            <div className="glow glow-two"/>
            <div className="grid-haze"/>
        </div>
    );
}
