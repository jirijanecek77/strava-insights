import {Fragment, useEffect, useMemo, useRef, useState} from "react";
import {Bar, Brush, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis} from "recharts";

import {adminStravaAthleteId} from "../constants";
import {aggregateTrendItems, buildCalendarWeeks, buildComparisonPeriodOptions, groupBestEffortsBySport, shiftMonth, sortComparisons} from "../utils/data";
import {
    formatComparisonRange,
    formatDateLabel,
    formatDateTime,
    formatDistanceMeters,
    formatDuration,
    formatHeartRateDrift,
    formatLabel,
    formatMetricValue,
    formatNumber,
    formatPaceSeconds,
    formatSportLabel,
    formatSyncProgress,
    formatThresholdSnapshotSummary,
    formatTrendAxisLabel,
} from "../utils/formatters";
import {ActivityDetail} from "./activity-detail";
import {EmptyState, FilterSelect} from "./common";

export function DashboardView({
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
                {trends ? <TrendList items={trends.items}/> : <EmptyState text="Rolling 30-day mode compares windows directly."/>}
            </article>
            <article className="panel panel-span-full">
                <div className="panel-header">
                    <div>
                        <p className="eyebrow">Overview</p>
                    </div>
                </div>
                {selectedWindow !== "rolling_30d" && comparisonOptions.length > 1 ? (
                    <div className="comparison-period-controls">
                        <FilterSelect label="Current" options={comparisonOptions} value={currentComparisonStart} onChange={onChangeCurrentComparisonStart}/>
                        <FilterSelect
                            label="Previous"
                            options={comparisonOptions.filter((option) => option.id !== currentComparisonStart)}
                            value={previousComparisonStart}
                            onChange={onChangePreviousComparisonStart}
                        />
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

export function CalendarView({activities, calendarMonth, onChangeMonth, onSelectActivity}) {
    const weeks = useMemo(() => buildCalendarWeeks(calendarMonth, activities), [activities, calendarMonth]);
    return (
        <section className="panel">
            <div className="panel-header">
                <div>
                    <p className="eyebrow">Calendar</p>
                    <h2>{calendarMonth.toLocaleDateString(undefined, {month: "long", year: "numeric"})}</h2>
                </div>
                <div className="calendar-controls">
                    <button className="ghost-button" onClick={() => onChangeMonth(shiftMonth(calendarMonth, -1))} type="button">Prev</button>
                    <button className="ghost-button" onClick={() => onChangeMonth(shiftMonth(calendarMonth, 1))} type="button">Next</button>
                </div>
            </div>
            <div className="calendar-grid">
                <div className="calendar-corner" aria-hidden="true"/>
                {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day) => (
                    <div className="calendar-head" key={day}>{day}</div>
                ))}
                {weeks.map((week) => (
                    <Fragment key={`week-${week.weekNumber}-${week.days[0].date.toISOString()}`}>
                        <div className="calendar-week-label" aria-label={`Week ${week.weekNumber}`}>{week.weekNumber}</div>
                        {week.days.map((day) => (
                            <div key={day.date.toISOString()} className={day.isCurrentMonth ? "calendar-cell" : "calendar-cell muted"}>
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

export function ActivitiesView({
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
                    <ActivityDetail detail={activityDetail} activeSeriesIndex={activeSeriesIndex} onSelectSeriesIndex={onSelectSeriesIndex}/>
                ) : null}
            </article>
        </section>
    );
}

export function BestEffortsView({items, selectedSport, onSelectActivity}) {
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

export function SettingsView({
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
    onSaveProfile,
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
                    <div className="settings-row"><span>Strava Athlete</span><strong>{user.strava_athlete_id}</strong></div>
                </div>
                <div className="profile-account-actions">
                    <button className="ghost-button inline-button logout-button" onClick={onLogout} type="button">Log out</button>
                </div>
                <section className="settings-section">
                    <div className="settings-section-header">
                        <div>
                            <p className="eyebrow">Thresholds</p>
                            <h3>Edit thresholds</h3>
                        </div>
                        <button className="ghost-button inline-button" onClick={onStartNewThresholdProfile} type="button">Create New Period</button>
                    </div>
                    <div className="profile-period-toolbar simple">
                        <div className={`threshold-selected-summary${!latestThresholdProfile || profileForm.effectiveFrom !== latestThresholdProfile.effective_from ? " is-draft" : ""}`}>
                            <strong>
                                {!latestThresholdProfile || profileForm.effectiveFrom !== latestThresholdProfile.effective_from
                                    ? "New period draft"
                                    : latestThresholdProfile?.effective_from ?? "No saved thresholds"}
                            </strong>
                            <span>
                                {!latestThresholdProfile || profileForm.effectiveFrom !== latestThresholdProfile.effective_from
                                    ? "Choose an effective date, update the fields, and save."
                                    : formatThresholdSnapshotSummary(latestThresholdProfile)}
                            </span>
                        </div>
                    </div>
                    <div className="threshold-form-grid">
                        <div className="threshold-metric-card threshold-date-card">
                            <p className="eyebrow">Effective Date</p>
                            <h4>Threshold period</h4>
                            <label className="control-chip">
                                <span>Effective From</span>
                                <input aria-label="Effective From" type="date" value={profileForm.effectiveFrom} onChange={(event) => onChangeProfileField("effectiveFrom", event.target.value)}/>
                            </label>
                        </div>
                        <div className="threshold-metric-card">
                            <p className="eyebrow">Heart Rate</p>
                            <h4>Threshold bpm</h4>
                            <div className="threshold-input-grid">
                                <label className="control-chip">
                                    <span>Aerobic Threshold HR (bpm)</span>
                                    <input aria-label="Aerobic Threshold HR (bpm)" inputMode="numeric" step="1" type="number" value={profileForm.aerobicThresholdHeartRate} onChange={(event) => onChangeProfileField("aerobicThresholdHeartRate", event.target.value)}/>
                                </label>
                                <label className="control-chip">
                                    <span>Anaerobic Threshold HR (bpm)</span>
                                    <input aria-label="Anaerobic Threshold HR (bpm)" inputMode="numeric" step="1" type="number" value={profileForm.anaerobicThresholdHeartRate} onChange={(event) => onChangeProfileField("anaerobicThresholdHeartRate", event.target.value)}/>
                                </label>
                            </div>
                        </div>
                        <div className="threshold-metric-card">
                            <p className="eyebrow">Pace</p>
                            <h4>Threshold min/km</h4>
                            <div className="threshold-input-grid">
                                <label className="control-chip">
                                    <span>Aerobic Threshold Pace (min/km)</span>
                                    <input aria-label="Aerobic Threshold Pace (min/km)" inputMode="text" placeholder="5:20" type="text" value={profileForm.aerobicThresholdPace} onChange={(event) => onChangeProfileField("aerobicThresholdPace", event.target.value)}/>
                                </label>
                                <label className="control-chip">
                                    <span>Anaerobic Threshold Pace (min/km)</span>
                                    <input aria-label="Anaerobic Threshold Pace (min/km)" inputMode="text" placeholder="4:15" type="text" value={profileForm.anaerobicThresholdPace} onChange={(event) => onChangeProfileField("anaerobicThresholdPace", event.target.value)}/>
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
                    <div className="settings-row"><span>Type</span><strong>{syncStatus?.sync_type ?? "n/a"}</strong></div>
                    <div className="settings-row"><span>Progress</span><strong>{formatSyncProgress(syncStatus)}</strong></div>
                    <div className="settings-row"><span>Started</span><strong>{syncStatus?.started_at ? formatDateTime(syncStatus.started_at) : "n/a"}</strong></div>
                    <div className="settings-row"><span>Finished</span><strong>{syncStatus?.finished_at ? formatDateTime(syncStatus.finished_at) : "n/a"}</strong></div>
                </div>
                <button className="ghost-button" disabled={syncBusy} onClick={onRefreshSync} type="button">
                    {syncBusy ? "Refreshing..." : "Refresh Sync"}
                </button>
            </article>
        </section>
    );
}

export function AdminView({actionUserId, adminUsers, busy, onDisableUser}) {
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
                                    <span className={isDisabled ? "status-pill is-disabled" : "status-pill is-active"}>{isDisabled ? "Disabled" : "Active"}</span>
                                </div>
                                <div className="admin-user-meta">
                                    <span>Last login</span>
                                    <strong>{item.last_login_at ? formatDateTime(item.last_login_at) : "Never"}</strong>
                                    <span>Created</span>
                                    <strong>{formatDateTime(item.created_at)}</strong>
                                </div>
                                <div className="admin-user-actions">
                                    {!isSelf ? (
                                        <button className="ghost-button" disabled={isDisabled || actionUserId === item.id} onClick={() => onDisableUser(item.id)} type="button">
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
                <span className="comparison-period-label">{formatComparisonRange(current?.period_start, previous?.period_start, periodType)}</span>
            </div>
            <MetricRow label="Distance" current={current?.total_distance_meters} previous={previous?.total_distance_meters} renderValue={formatDistanceMeters}/>
            <MetricRow label="Moving Time" current={current?.total_moving_time_seconds} previous={previous?.total_moving_time_seconds} renderValue={formatDuration}/>
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
    const periodType = items[0]?.period_type ?? "month";
    const chartData = points.map((point) => ({...point, axisLabel: formatTrendAxisLabel(point.periodStart, periodType)}));

    return (
        <div className="trend-chart-shell">
            <div className="trend-chart-legend" aria-hidden="true">
                <span className="trend-legend-item"><span className="trend-legend-swatch distance"/>Km</span>
                <span className="trend-legend-item"><span className="trend-legend-swatch sessions"/>Sessions</span>
                <span className="trend-legend-item"><span className="trend-legend-swatch hr-drift"/>HR Drift</span>
            </div>
            <div aria-label="Trend graph" className="trend-chart" role="img">
                <ResponsiveContainer height="100%" width="100%">
                    <ComposedChart data={chartData} margin={{top: 8, right: 12, bottom: 8, left: 0}}>
                        <CartesianGrid stroke="rgba(31, 41, 55, 0.10)" strokeDasharray="3 4" vertical={false}/>
                        <XAxis axisLine={false} dataKey="axisLabel" tick={{fill: "#6f6b62", fontSize: 11}} tickLine={false}/>
                        <YAxis axisLine={false} domain={[0, "dataMax"]} tick={{fill: "#6f6b62", fontSize: 11}} tickFormatter={(value) => `${Math.round(value)}`} tickLine={false} width={28}/>
                        <YAxis axisLine={false} dataKey="sessions" domain={[0, "dataMax"]} hide orientation="right" yAxisId="sessions"/>
                        <YAxis axisLine={false} dataKey="hrDrift" domain={["dataMin", "dataMax"]} hide orientation="right" yAxisId="hrDrift"/>
                        <Tooltip content={<TrendChartTooltip/>} cursor={{fill: "rgba(252, 76, 2, 0.08)"}}/>
                        <Bar dataKey="distanceKm" fill="#fc4c02" maxBarSize={42} radius={[10, 10, 4, 4]}/>
                        <Line dataKey="sessions" dot={{fill: "#1d7af3", r: 4, stroke: "#ffffff", strokeWidth: 2}} stroke="#1d7af3" strokeWidth={2} type="monotone" yAxisId="sessions"/>
                        <Line connectNulls dataKey="hrDrift" dot={{fill: "#2f9e44", r: 4, stroke: "#ffffff", strokeWidth: 2}} stroke="#2f9e44" strokeWidth={2} type="monotone" yAxisId="hrDrift"/>
                        <Brush dataKey="axisLabel" defaultEndIndex={points.length - 1} defaultStartIndex={Math.max(points.length - 12, 0)} fill="rgba(252, 76, 2, 0.08)" height={22} stroke="#fc4c02" travellerWidth={12}/>
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
