import {useEffect, useMemo, useRef, useState} from "react";
import {
    Area,
    CartesianGrid,
    ComposedChart,
    Line,
    ReferenceArea,
    ReferenceDot,
    ReferenceLine,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from "recharts";

import {
    buildThresholdGuides,
    computeDetailTooltipPosition,
    downsampleChartData,
    expandChartDomain,
    findClosestDistanceIndex,
    findClosestPointIndex,
    resolveDetailReferenceValue,
} from "../utils/data";
import {
    formatAltitudeAxisValue,
    formatAxisValue,
    formatBandDistribution,
    formatClimbingSummary,
    formatDateTime,
    formatDistanceKm,
    formatHeartRateDrift,
    formatNumber,
    formatPercentage,
    formatSummaryMetricDisplay,
    formatTooltipSeriesValue,
} from "../utils/formatters";
import {EmptyState} from "./common";

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

export function ActivityDetail({detail, activeSeriesIndex, onSelectSeriesIndex}) {
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
                <MetricTile label="Distance" value={detail.kpis.distance_km != null ? `${detail.kpis.distance_km} km` : "n/a"}/>
                <MetricTile label="Moving Time" value={detail.kpis.moving_time_display ?? "n/a"}/>
                <MetricTile label={detail.kpis.summary_metric_kind === "speed" ? "Speed" : "Pace"} value={formatSummaryMetricDisplay(detail.kpis.summary_metric_display, detail.kpis.summary_metric_kind)}/>
                <MetricTile label="Elevation" value={detail.kpis.total_elevation_gain_meters != null ? `${detail.kpis.total_elevation_gain_meters} m` : "n/a"}/>
                <MetricTile label="Average HR" value={detail.kpis.average_heartrate_bpm != null ? `${detail.kpis.average_heartrate_bpm} bpm` : "n/a"}/>
                {isRide ? <MetricTile label="Cadence" value={detail.kpis.average_cadence != null ? `${formatNumber(detail.kpis.average_cadence)} rpm` : "n/a"}/> : null}
                <MetricTile label="HR Drift" value={formatHeartRateDrift(detail.kpis.heart_rate_drift_bpm)}/>
            </div>
            <div className="detail-grid">
                <div className="detail-card detail-card-wide">
                    <p className="eyebrow">Route</p>
                    <MapPanel activeIndex={resolvedActiveIndex} onSelectIndex={onSelectSeriesIndex} polyline={routePoints}/>
                </div>
                <DetailChart accent="orange" activeIndex={resolvedActiveIndex} altitudeValues={detail.series.altitude_meters} distanceValues={detail.series.distance_km} label={detail.series.pace_minutes_per_km.length ? "Pace" : "Speed"} onSelectIndex={onSelectSeriesIndex} referenceValue={paceReferenceValue} thresholds={detail.thresholds} valueKind={detail.series.pace_minutes_per_km.length ? "pace" : "speed"} values={paceOrSpeed}/>
                <DetailChart accent="red" activeIndex={resolvedActiveIndex} altitudeValues={detail.series.altitude_meters} distanceValues={detail.series.distance_km} label="Heart Rate" onSelectIndex={onSelectSeriesIndex} referenceValue={heartRateReferenceValue} thresholds={detail.thresholds} valueKind="heart_rate" values={detail.series.moving_average_heartrate}/>
                <DetailChart accent="green" activeIndex={resolvedActiveIndex} altitudeValues={detail.series.altitude_meters} distanceValues={detail.series.distance_km} label="Slope" onSelectIndex={onSelectSeriesIndex} referenceValue={slopeReferenceValue} valueKind="slope" values={detail.series.slope_percent}/>
            </div>
            <div className="detail-analysis-grid">
                <div className="detail-card">
                    <p className="eyebrow">{isRide ? "Cycling Analysis" : "Running Analysis"}</p>
                    {isRun && detail.running_analysis ? <RunningAnalysisCard analysis={detail.running_analysis}/> : null}
                    {isRun && !detail.running_analysis ? <EmptyState compact text="Add AeT and AnT pace and heart-rate thresholds in Settings to unlock running analysis."/> : null}
                    {isRide && detail.cycling_analysis ? <CyclingAnalysisCard analysis={detail.cycling_analysis}/> : null}
                    {isRide && !detail.cycling_analysis ? <EmptyState compact text="Cycling analysis needs ride speed data. Add heart-rate thresholds in Settings to unlock HR-based ride intensity metrics."/> : null}
                </div>
            </div>
        </div>
    );
}

function DetailChart({accent, activeIndex, altitudeValues, distanceValues, label, onSelectIndex, referenceValue, thresholds, valueKind, values}) {
    return (
        <div className="detail-card">
            <p className="eyebrow">{label}</p>
            <MiniLineChart accent={accent} activeIndex={activeIndex} altitudeValues={altitudeValues} distanceValues={distanceValues} label={label} onSelectIndex={onSelectIndex} referenceValue={referenceValue} thresholds={thresholds} valueKind={valueKind} values={values}/>
        </div>
    );
}

function RunningAnalysisCard({analysis}) {
    return (
        <div className="settings-list">
            <div className="settings-row"><MetricHelpLabel label="Pace Bands" tooltipKey="pace_bands"/><strong>{formatBandDistribution(analysis.pace_distribution)}</strong></div>
            <div className="settings-row"><MetricHelpLabel label="HR Bands" tooltipKey="hr_bands"/><strong>{formatBandDistribution(analysis.heart_rate_distribution)}</strong></div>
            <div className="settings-row"><MetricHelpLabel label="Agreement" tooltipKey="agreement"/><strong>{formatPercentage(analysis.agreement.matching_share_percent)}</strong></div>
            <div className="settings-row"><MetricHelpLabel label="Pace Above HR" tooltipKey="pace_above_hr"/><strong>{formatPercentage(analysis.agreement.pace_higher_share_percent)}</strong></div>
            <div className="settings-row"><MetricHelpLabel label="HR Above Pace" tooltipKey="hr_above_pace"/><strong>{formatPercentage(analysis.agreement.heart_rate_higher_share_percent)}</strong></div>
            <div className="settings-row"><MetricHelpLabel label="Longest AeT to AnT" tooltipKey="longest_aet_to_ant"/><strong>{formatDistanceKm(analysis.steady_threshold_block.distance_km)}</strong></div>
            <div className="settings-row"><MetricHelpLabel label="Longest Above AnT" tooltipKey="longest_above_ant"/><strong>{formatDistanceKm(analysis.above_threshold_block.distance_km)}</strong></div>
            <div className="settings-row"><span>Activity Evaluation</span><span className="running-analysis-copy">{analysis.activity_evaluation}</span></div>
            <div className="settings-row"><span>Further Training Suggestion</span><span className="running-analysis-copy">{analysis.further_training_suggestion}</span></div>
        </div>
    );
}

function CyclingAnalysisCard({analysis}) {
    return (
        <div className="settings-list">
            <div className="settings-row"><MetricHelpLabel label="Speed Bands" tooltipKey="speed_bands" tooltipMap={CYCLING_ANALYSIS_TOOLTIPS}/><strong>{formatBandDistribution(analysis.speed_distribution)}</strong></div>
            {analysis.heart_rate_distribution ? <div className="settings-row"><MetricHelpLabel label="HR Bands" tooltipKey="hr_bands" tooltipMap={CYCLING_ANALYSIS_TOOLTIPS}/><strong>{formatBandDistribution(analysis.heart_rate_distribution)}</strong></div> : null}
            <div className="settings-row"><MetricHelpLabel label="Climbing Share" tooltipKey="climbing_share" tooltipMap={CYCLING_ANALYSIS_TOOLTIPS}/><strong>{formatClimbingSummary(analysis.climbing_summary)}</strong></div>
            {analysis.steady_aerobic_block ? <div className="settings-row"><MetricHelpLabel label="Longest Aerobic Block" tooltipKey="longest_aerobic_block" tooltipMap={CYCLING_ANALYSIS_TOOLTIPS}/><strong>{formatDistanceKm(analysis.steady_aerobic_block.distance_km)}</strong></div> : null}
            {analysis.above_threshold_block ? <div className="settings-row"><MetricHelpLabel label="Longest Above AnT" tooltipKey="longest_above_ant" tooltipMap={CYCLING_ANALYSIS_TOOLTIPS}/><strong>{formatDistanceKm(analysis.above_threshold_block.distance_km)}</strong></div> : null}
            <div className="settings-row"><MetricHelpLabel label="Average Cadence" tooltipKey="average_cadence" tooltipMap={CYCLING_ANALYSIS_TOOLTIPS}/><strong>{analysis.average_cadence != null ? `${formatNumber(analysis.average_cadence)} rpm` : "n/a"}</strong></div>
            <div className="settings-row"><span>Activity Evaluation</span><span className="running-analysis-copy">{analysis.activity_evaluation}</span></div>
            <div className="settings-row"><span>Further Training Suggestion</span><span className="running-analysis-copy">{analysis.further_training_suggestion}</span></div>
        </div>
    );
}

function MetricHelpLabel({label, tooltipKey, tooltipMap = RUNNING_ANALYSIS_TOOLTIPS}) {
    const [open, setOpen] = useState(false);
    const tooltipId = `tooltip-${tooltipKey}`;
    return (
        <span className="metric-help-label">
            <span>{label}</span>
            <button aria-describedby={open ? tooltipId : undefined} aria-label={`${label} explanation`} className="info-tooltip-trigger" onBlur={() => setOpen(false)} onFocus={() => setOpen(true)} onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)} type="button">?</button>
            {open ? <span className="info-tooltip-panel" id={tooltipId} role="tooltip">{tooltipMap[tooltipKey]}</span> : null}
        </span>
    );
}

function DetailChartTooltip({active, label, payload, position, valueKind}) {
    const point = payload?.[0]?.payload;
    if (!active || !point) {
        return null;
    }
    return (
        <div className="detail-chart-tooltip" style={{left: `${position.leftPercent}%`, top: `${position.topPercent}%`, transform: position.preferBelow ? "translate(-50%, 12px)" : "translate(-50%, calc(-100% - 12px))"}}>
            <span>Distance: {formatNumber(point.distance)} km</span>
            <span>{label}: {formatTooltipSeriesValue(valueKind, point.value)}</span>
        </div>
    );
}

function MetricTile({label, value}) {
    return <div className="metric-tile"><span>{label}</span><strong>{value}</strong></div>;
}

function MiniLineChart({accent, activeIndex, altitudeValues, distanceValues, label, onSelectIndex, referenceValue, thresholds, valueKind, values}) {
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
    const numericValues = useMemo(() => chartData.map((point) => point.value).filter(Number.isFinite), [chartData]);
    const numericDistances = useMemo(() => chartData.map((point) => point.distance).filter(Number.isFinite), [chartData]);
    const numericAltitudes = useMemo(() => chartData.map((point) => point.altitude).filter(Number.isFinite), [chartData]);
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
    const {xMax, xMin} = useMemo(() => ({xMax: Math.max(...numericDistances), xMin: Math.min(...numericDistances)}), [numericDistances]);
    const thresholdGuides = useMemo(() => buildThresholdGuides({maxValue, minValue, thresholds, valueKind, xMax, xMin}), [maxValue, minValue, thresholds, valueKind, xMax, xMin]);
    const clampedActiveIndex = activeIndex == null ? null : Math.min(activeIndex, chartData.length - 1);
    const activePoint = useMemo(() => (clampedActiveIndex == null ? null : chartData[clampedActiveIndex]), [chartData, clampedActiveIndex]);
    const [isTooltipVisible, setIsTooltipVisible] = useState(false);
    const gradientId = `detail-elevation-${accent}-${valueKind}`;

    useEffect(() => {
        if (!activePoint || !Number.isFinite(activePoint.distance) || !Number.isFinite(activePoint.value)) {
            setIsTooltipVisible(false);
            return undefined;
        }
        setIsTooltipVisible(true);
        const timeoutId = window.setTimeout(() => setIsTooltipVisible(false), 1600);
        return () => window.clearTimeout(timeoutId);
    }, [activePoint]);

    const tooltipPosition = useMemo(() => computeDetailTooltipPosition({activePoint, maxValue, minValue, valueKind, xMax, xMin}), [activePoint, maxValue, minValue, valueKind, xMax, xMin]);

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
                <DetailChartTooltip active label={label} payload={[{payload: activePoint}]} position={tooltipPosition} valueKind={valueKind}/>
            ) : null}
            <ResponsiveContainer height="100%" width="100%">
                <ComposedChart data={sampledChartData} margin={{top: 10, right: 10, bottom: 16, left: 2}} onClick={handleChartSelection} onMouseMove={handleChartSelection} syncId="activity-detail-series">
                    <defs>
                        <linearGradient id={gradientId} x1="0" x2="0" y1="0" y2="1">
                            <stop offset="0%" stopColor="rgba(100, 116, 139, 0.35)"/>
                            <stop offset="100%" stopColor="rgba(100, 116, 139, 0.08)"/>
                        </linearGradient>
                    </defs>
                    <CartesianGrid stroke="rgba(31, 41, 55, 0.10)" strokeDasharray="3 4" vertical={false}/>
                    <XAxis axisLine={false} dataKey="distance" domain={[xMin, xMax]} tick={{fill: "#6f6b62", fontSize: 11}} tickFormatter={(value) => Math.round(value)} tickLine={false} type="number"/>
                    <YAxis axisLine={false} domain={[minValue, maxValue]} reversed={valueKind === "pace"} tick={{fill: "#6f6b62", fontSize: 11}} tickFormatter={(value) => formatAxisValue(valueKind, value)} tickLine={false} width={34}/>
                    <YAxis axisLine={false} dataKey="altitude" domain={["dataMin", "dataMax"]} hide={!numericAltitudes.length} orientation="right" tick={{fill: "rgba(100, 116, 139, 0.88)", fontSize: 10}} tickFormatter={formatAltitudeAxisValue} tickLine={false} width={30} yAxisId="altitude"/>
                    <Tooltip content={() => null} cursor={{stroke: "rgba(29, 122, 243, 0.28)", strokeDasharray: "4 4"}}/>
                    {thresholdGuides.bands.map((band) => (
                        <ReferenceArea key={`threshold-band-${valueKind}-${band.code}`} fill={band.color} fillOpacity={0.1} ifOverflow="extendDomain" x1={xMin} x2={xMax} y1={band.y1} y2={band.y2}/>
                    ))}
                    <Area dataKey="altitude" fill={`url(#${gradientId})`} isAnimationActive={false} stroke="rgba(100, 116, 139, 0.28)" strokeWidth={1} type="monotone" yAxisId="altitude"/>
                    <Line activeDot={false} connectNulls dataKey="value" dot={false} isAnimationActive={false} stroke={lineColor} strokeWidth={2.25} type="monotone"/>
                    {Number.isFinite(referenceValue) ? <ReferenceLine ifOverflow="extendDomain" stroke={referenceLineColor} strokeDasharray="5 5" strokeWidth={1.5} y={referenceValue}/> : null}
                    {thresholdGuides.lines.map((line) => (
                        <ReferenceLine ifOverflow="extendDomain" key={`threshold-line-${valueKind}-${line.label}`} label={{fill: line.color, fontSize: 10, position: "insideTopRight", value: line.label}} stroke={line.color} strokeDasharray="3 4" strokeWidth={1} y={line.value}/>
                    ))}
                    {activePoint && Number.isFinite(activePoint.distance) ? <ReferenceLine stroke="rgba(29, 122, 243, 0.32)" strokeDasharray="4 4" x={activePoint.distance}/> : null}
                    {activePoint && Number.isFinite(activePoint.distance) && Number.isFinite(activePoint.value) ? <ReferenceDot fill="#ffffff" r={4} stroke={lineColor} strokeWidth={2} x={activePoint.distance} y={activePoint.value}/> : null}
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
            {mapState !== "ready" ? <div className="map-header-note">{mapyApiKey ? "Mapy.cz tiles unavailable, route preview fallback active." : "Route preview fallback active."}</div> : null}
            <div className={mapState === "fallback" || !mapyApiKey ? "mapycz-canvas hidden" : "mapycz-canvas"} ref={mapContainerRef}/>
            {mapState !== "ready" ? (
                <>
                    {mapyApiKey ? <div className="map-loading-note">Mapy.cz background tiles could not be loaded. Check that the API key is valid, has Map Tiles access, and allows `http://localhost:5173`.</div> : null}
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
        <svg aria-label="Route preview" className="route-map" onClick={handlePointer} preserveAspectRatio="none" viewBox="0 0 100 100">
            <polyline fill="none" points={coordinates.map(({x, y}) => `${x},${y}`).join(" ")} strokeWidth="2"/>
            <circle cx={coordinates[0].x} cy={coordinates[0].y} r="2.4"/>
            {activePoint ? <circle className="active-route-point" cx={activePoint.x} cy={activePoint.y} r="3.2"/> : null}
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
            attribution: '&copy; <a href="https://api.mapy.com/copyright" target="_blank" rel="noreferrer">Mapy.com</a>',
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
        const map = L.map(container, {attributionControl: false, zoomControl: true});

        L.tileLayer(tileConfig.urlTemplate, {minZoom: tileConfig.minZoom, maxZoom: tileConfig.maxZoom, tileSize: tileConfig.tileSize, attribution: tileConfig.attribution}).addTo(map);

        const route = L.polyline(coordinates, {color: "#fc4c02", weight: 3, opacity: 0.95}).addTo(map);
        const activeMarker = L.circleMarker(coordinates[0], {color: "#1d7af3", fillColor: "#1d7af3", fillOpacity: 1, radius: 6, weight: 2}).addTo(map);

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
                activeMarker.setLatLng(coordinates[Math.min(activeIndex, coordinates.length - 1)]);
            },
        };
    } catch {
        return null;
    }
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
