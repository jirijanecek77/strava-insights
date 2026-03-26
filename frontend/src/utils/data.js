import {formatComparisonPeriod} from "./formatters";

export function buildQuery(params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
        if (value != null && value !== "") {
            searchParams.set(key, value);
        }
    });
    const query = searchParams.toString();
    return query ? `?${query}` : "";
}

export function isSyncInFlight(syncStatus) {
    return syncStatus?.status === "queued" || syncStatus?.status === "running";
}

export function aggregateTrendItems(items) {
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

export function parseMonthInput(value) {
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

export function buildComparisonPeriodOptions(items, periodType) {
    const uniqueStarts = Array.from(new Set(items.map((item) => item.period_start))).sort((left, right) => right.localeCompare(left));
    return uniqueStarts.map((value) => ({
        id: value,
        label: formatComparisonPeriod(value, periodType),
    }));
}

export function sortComparisons(items) {
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

export function findClosestPointIndex(points, target, mode = "xy") {
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

export function startOfMonth(value) {
    return new Date(value.getFullYear(), value.getMonth(), 1);
}

export function shiftMonth(value, delta) {
    return new Date(value.getFullYear(), value.getMonth() + delta, 1);
}

export function formatLocalDateKey(value) {
    const year = value.getFullYear();
    const month = String(value.getMonth() + 1).padStart(2, "0");
    const day = String(value.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
}

export function buildCalendarDays(calendarMonth, activities) {
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

export function groupBestEffortsBySport(items) {
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

export function buildCalendarWeeks(calendarMonth, activities) {
    const days = buildCalendarDays(calendarMonth, activities);
    return Array.from({length: days.length / 7}, (_, index) => {
        const weekDays = days.slice(index * 7, (index + 1) * 7);
        return {
            days: weekDays,
            weekNumber: getIsoWeek(weekDays[0].date),
        };
    });
}

export function buildCalendarSummary(dayActivities) {
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

export function expandChartDomain(minValue, maxValue) {
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

export function downsampleChartData(points, focusIndex, maxPoints = 240) {
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

export function findClosestDistanceIndex(points, targetDistance) {
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

export function computeDetailTooltipPosition({activePoint, maxValue, minValue, valueKind, xMax, xMin}) {
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

function averageSeriesValue(values) {
    const numericValues = (values ?? []).map((value) => Number(value)).filter(Number.isFinite);
    if (!numericValues.length) {
        return null;
    }
    return numericValues.reduce((sum, value) => sum + value, 0) / numericValues.length;
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

function getIsoWeek(value) {
    const date = new Date(Date.UTC(value.getFullYear(), value.getMonth(), value.getDate()));
    const day = date.getUTCDay() || 7;
    date.setUTCDate(date.getUTCDate() + 4 - day);
    const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
    return Math.ceil((((date - yearStart) / 86400000) + 1) / 7);
}
