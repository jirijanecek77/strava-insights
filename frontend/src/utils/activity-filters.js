export const activityFilterOperators = [
    {id: "gt", label: ">"},
    {id: "lt", label: "<"},
    {id: "eq", label: "="},
];

// `read` returns the comparable number from an activity list row, `parse` turns user input into the same unit,
// and `precision` is the rounding used for "=" so it matches what the UI displays.
export const activityFilterKpis = [
    {
        id: "distance",
        label: "Distance",
        unit: "km",
        precision: 1,
        read: (activity) => toNumber(activity.distance_km),
        parse: parseDecimal,
    },
    {
        id: "moving_time",
        label: "Moving time",
        unit: "min",
        precision: 0,
        read: (activity) => {
            const seconds = toNumber(activity.moving_time_seconds);
            return seconds == null ? null : seconds / 60;
        },
        parse: parseDecimal,
    },
    {
        id: "elevation",
        label: "Elevation",
        unit: "m",
        precision: 0,
        read: (activity) => toNumber(activity.total_elevation_gain_meters),
        parse: parseDecimal,
    },
    {
        id: "heart_rate",
        label: "Avg HR",
        unit: "bpm",
        precision: 0,
        read: (activity) => toNumber(activity.average_heartrate_bpm),
        parse: parseDecimal,
    },
    {
        id: "efficiency",
        label: "Efficiency",
        unit: "m/beat",
        precision: 2,
        read: (activity) => toNumber(activity.aerobic_efficiency_m_per_beat),
        parse: parseDecimal,
    },
    {
        id: "pace",
        label: "Pace",
        unit: "min/km",
        metricKind: "pace",
        precision: 0,
        read: (activity) => (activity.summary_metric_kind === "pace" ? toNumber(activity.average_pace_seconds_per_km) : null),
        parse: parsePaceSeconds,
        formatValue: formatPaceInput,
    },
    {
        id: "speed",
        label: "Speed",
        unit: "km/h",
        metricKind: "speed",
        precision: 1,
        read: (activity) => (activity.summary_metric_kind === "speed" ? toNumber(activity.average_speed_kph) : null),
        parse: parseDecimal,
    },
];

const kpisById = Object.fromEntries(activityFilterKpis.map((kpi) => [kpi.id, kpi]));
const operatorsById = Object.fromEntries(activityFilterOperators.map((operator) => [operator.id, operator]));

// Pace and speed are offered only when the loaded activities use that summary metric, so the choice follows the sport.
export function resolveAvailableFilterKpis(activities) {
    const metricKinds = new Set(activities.map((activity) => activity.summary_metric_kind).filter(Boolean));
    return activityFilterKpis.filter((kpi) => kpi.metricKind == null || metricKinds.has(kpi.metricKind));
}

export function buildActivityFilterRule(kpiId, operatorId, rawValue) {
    const kpi = kpisById[kpiId];
    if (!kpi || !operatorsById[operatorId]) {
        return null;
    }
    const value = kpi.parse(rawValue);
    if (value == null) {
        return null;
    }
    return {kpi: kpiId, operator: operatorId, value};
}

export function formatActivityFilterRule(rule) {
    const kpi = kpisById[rule.kpi];
    const operator = operatorsById[rule.operator];
    const value = kpi.formatValue ? kpi.formatValue(rule.value) : String(rule.value);
    return `${kpi.label} ${operator.label} ${value} ${kpi.unit}`;
}

export function filterActivities(activities, {name = "", rules = []} = {}) {
    const needle = name.trim().toLocaleLowerCase();
    return activities.filter((activity) => {
        if (needle && !(activity.name ?? "").toLocaleLowerCase().includes(needle)) {
            return false;
        }
        return rules.every((rule) => matchesRule(activity, rule));
    });
}

function matchesRule(activity, rule) {
    const kpi = kpisById[rule.kpi];
    if (!kpi) {
        return true;
    }
    const actual = kpi.read(activity);
    if (actual == null) {
        return false;
    }
    if (rule.operator === "gt") {
        return actual > rule.value;
    }
    if (rule.operator === "lt") {
        return actual < rule.value;
    }
    return roundTo(actual, kpi.precision) === roundTo(rule.value, kpi.precision);
}

function roundTo(value, precision) {
    const factor = 10 ** precision;
    return Math.round(value * factor) / factor;
}

function toNumber(value) {
    if (value == null || value === "") {
        return null;
    }
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : null;
}

function parseDecimal(rawValue) {
    const normalized = String(rawValue ?? "").trim().replace(",", ".");
    if (!normalized) {
        return null;
    }
    return toNumber(normalized);
}

// Accepts "4:30" or decimal minutes such as "4.5" and returns seconds per km.
function parsePaceSeconds(rawValue) {
    const normalized = String(rawValue ?? "").trim();
    const clockMatch = normalized.match(/^(\d+):([0-5]?\d)$/);
    if (clockMatch) {
        return Number(clockMatch[1]) * 60 + Number(clockMatch[2]);
    }
    const minutes = parseDecimal(normalized);
    return minutes == null ? null : Math.round(minutes * 60);
}

function formatPaceInput(seconds) {
    const rounded = Math.round(seconds);
    return `${Math.floor(rounded / 60)}:${String(rounded % 60).padStart(2, "0")}`;
}
