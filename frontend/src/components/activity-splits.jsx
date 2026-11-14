import {useEffect, useId, useMemo, useState} from "react";
import {Area, CartesianGrid, ComposedChart, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis} from "recharts";

import {buildSplitChartData, closestSplitStreamIndex, splitAtDistance} from "../utils/activity-splits";
import {formatAltitudeAxisValue, formatAxisValue, formatDuration, formatNumber, formatTooltipSeriesValue} from "../utils/formatters";
import {EmptyState} from "./common";

export function ActivitySplitsChart({splits, series, isRun, activeIndex, onSelectIndex}) {
    const chartId = useId();
    const paceGradientId = `split-pace-${chartId}`;
    const elevationGradientId = `split-elevation-${chartId}`;
    const laps = splits?.laps ?? [];
    const [hoverDistance, setHoverDistance] = useState(null);
    const [tooltipVisible, setTooltipVisible] = useState(false);
    useEffect(() => {
        setHoverDistance((current) => closestSplitStreamIndex(series.distance_km, current) === activeIndex ? current : null);
    }, [activeIndex, splits, series.distance_km]);
    const data = useMemo(() => buildSplitChartData(laps, series.distance_km, series.altitude_meters, isRun),
        [laps, series.distance_km, series.altitude_meters, isRun]);
    useEffect(() => {
        if (!tooltipVisible) return undefined;
        const timer = window.setTimeout(() => setTooltipVisible(false), 1600);
        return () => window.clearTimeout(timer);
    }, [activeIndex, hoverDistance, tooltipVisible]);
    const distance = hoverDistance ?? series.distance_km[activeIndex];
    const focused = splitAtDistance(laps, distance);
    const ascent = focused?.elevation_gain_meters ?? null;
    const descent = focused?.elevation_loss_meters ?? null;
    const lapType = focused?.lap_type?.toLowerCase();
    const netElevation = ascent != null && descent != null ? Math.round(ascent - descent) : null;
    const metricName = isRun ? "Avg pace" : "Avg speed";
    const hasMetric = data.some((point) => point.metric != null);
    const hasElevation = data.some((point) => point.altitude != null);
    const altitude = series.altitude_meters[closestSplitStreamIndex(series.distance_km, distance)];
    const xMin = data[0]?.distance ?? 0;
    const xMax = data.at(-1)?.distance ?? 1;
    const focusPercent = Math.min(98, Math.max(2, 100 * (distance - xMin) / (xMax - xMin || 1)));

    function selectDistance(state) {
        if (state?.activeLabel == null) return;
        const selected = Number(state.activeLabel);
        if (!Number.isFinite(selected)) return;
        setHoverDistance(selected);
        setTooltipVisible(true);
        const index = closestSplitStreamIndex(series.distance_km, selected);
        if (index >= 0) onSelectIndex?.(index);
    }

    const unavailableText = "No usable recorded splits available.";

    return (
        <section aria-label="Activity splits" className="detail-card">
            <p className="eyebrow">Splits</p>
            {!data.length || !hasMetric ? <EmptyState compact text={unavailableText}/> : <>
                <div aria-label="Splits chart" className="mini-chart splits-chart" role="img">
                    {tooltipVisible && focused ? <div className="detail-chart-tooltip splits-tooltip" style={{left: `clamp(0.5rem, calc(${focusPercent}% - 6rem), calc(100% - 12.5rem))`, top: 8}}>
                        <span>Lap {focused.number}{focused.lap_type ? ` · ${focused.lap_type.toLowerCase()}` : ""}</span>
                        {focused.duration_seconds != null ? <span>Time: {formatDuration(Math.round(focused.duration_seconds))}</span> : null}
                        <span>{metricName}: {isRun
                            ? focused.average_pace_seconds_per_km != null ? formatTooltipSeriesValue("pace", focused.average_pace_seconds_per_km / 60) : "n/a"
                            : focused.average_speed_kph != null ? `${formatNumber(focused.average_speed_kph)} km/h` : "n/a"}</span>
                        {focused.average_heartrate_bpm != null ? <span>Avg HR: {Math.round(focused.average_heartrate_bpm)} bpm</span> : null}
                        {ascent != null || descent != null ? <span aria-label="Split ascent and descent">
                            ↑ {ascent != null ? `${Math.round(ascent)} m` : "n/a"} / ↓ {descent != null ? `${Math.round(descent)} m` : "n/a"}
                        </span> : null}
                        {netElevation != null ? <span
                            aria-label="Split net elevation change">Net: {netElevation >= 0 ? "+" : ""}{netElevation} m</span> : null}
                        {typeof altitude === "number" && Number.isFinite(altitude) ? <span>Elevation: {formatAltitudeAxisValue(altitude)}</span> : null}
                    </div> : null}
                    <ResponsiveContainer width="100%" height="100%">
                        <ComposedChart data={data} margin={{top: 10, right: 10, bottom: 16, left: 2}}
                                       onClick={selectDistance} onMouseMove={selectDistance} onMouseLeave={() => setTooltipVisible(false)}>
                            <defs>
                                <linearGradient id={paceGradientId} x1="0" x2="0" y1="0" y2="1">
                                    <stop offset="0%" stopColor="rgba(252, 76, 2, 0.22)"/>
                                    <stop offset="100%" stopColor="rgba(252, 76, 2, 0.04)"/>
                                </linearGradient>
                                <linearGradient id={elevationGradientId} x1="0" x2="0" y1="0" y2="1">
                                    <stop offset="0%" stopColor="rgba(100, 116, 139, 0.35)"/>
                                    <stop offset="100%" stopColor="rgba(100, 116, 139, 0.08)"/>
                                </linearGradient>
                            </defs>
                            <CartesianGrid stroke="rgba(31, 41, 55, 0.10)" strokeDasharray="3 4" vertical={false}/>
                            <XAxis allowDecimals={false} dataKey="distance" type="number" domain={[xMin, xMax]}
                                   axisLine={false} tickLine={false}
                                   tick={{fill: "#6f6b62", fontSize: 11}} tickFormatter={formatNumber}
                                   tickCount={25} minTickGap={8} interval="preserveStartEnd"/>
                            <YAxis yAxisId="metric" hide={!hasMetric} reversed={isRun} domain={["auto", "auto"]}
                                   interval={0} tickCount={5}
                                   axisLine={false} tickLine={false} width={42} tick={{fill: "#6f6b62", fontSize: 11}}
                                   tickFormatter={(value) => formatAxisValue(isRun ? "pace" : "speed", Number(value))}/>
                            <YAxis yAxisId="altitude" dataKey="altitude" hide={!hasElevation} orientation="right" domain={["dataMin", "dataMax"]}
                                   axisLine={false} tickLine={false} width={30} tick={{fill: "rgba(100, 116, 139, 0.88)", fontSize: 10}}
                                   tickFormatter={formatAltitudeAxisValue}/>
                            <Tooltip content={() => null} cursor={false}/>
                            {hasElevation ? <Area yAxisId="altitude" dataKey="altitude" type="monotone" connectNulls={false}
                                                  stroke="rgba(100, 116, 139, 0.28)" fill={`url(#${elevationGradientId})`} isAnimationActive={false}/> : null}
                            {focused ? <ReferenceArea yAxisId="metric" x1={focused.start_distance_meters / 1000}
                                                      x2={focused.end_distance_meters / 1000} fill="#fc4c02" fillOpacity={0.05}/> : null}
                            {laps.filter((lap) => lap.distance_meters > 0).map((lap) => <ReferenceLine key={lap.number}
                                yAxisId="metric" x={lap.start_distance_meters / 1000} stroke="rgba(100,116,139,0.18)" strokeDasharray="2 4"/>)}
                            <Area yAxisId="metric" dataKey="metric" type="stepAfter" connectNulls={false} dot={false}
                                  activeDot={false} stroke="#fc4c02" strokeWidth={2.25} fill={`url(#${paceGradientId})`}
                                  baseValue={isRun ? "dataMax" : "dataMin"} isAnimationActive={false}/>
                            {focused ? <ReferenceLine yAxisId="metric" x={distance} stroke="rgba(29,122,243,0.5)" strokeDasharray="4 4"/> : null}
                        </ComposedChart>
                    </ResponsiveContainer>
                </div>
            </>}
        </section>
    );
}
