export function formatLabel(value) {
    return String(value)
        .replace(/_/g, " ")
        .replace(/-/g, " ")
        .replace(/\b\w/g, (character) => character.toUpperCase());
}

export function formatMetricValue(value, suffix = "") {
    if (value == null) {
        return "n/a";
    }
    return `${formatNumber(value)}${suffix ? ` ${suffix}` : ""}`;
}

export function formatDistanceMeters(value) {
    if (value == null) {
        return "n/a";
    }
    return `${formatNumber(Number(value) / 1000)} km`;
}

export function formatNumber(value) {
    const numeric = Number(value);
    if (Number.isNaN(numeric)) {
        return String(value);
    }
    return numeric.toLocaleString(undefined, {maximumFractionDigits: 2});
}

export function formatDuration(totalSeconds) {
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

export function formatPaceSeconds(value) {
    if (value == null) {
        return "n/a";
    }
    const numeric = Number(value);
    const minutes = Math.floor(numeric / 60);
    const seconds = Math.round(numeric % 60);
    return `${minutes}:${String(seconds).padStart(2, "0")} /km`;
}

export function formatDateTime(value) {
    return new Date(value).toLocaleString(undefined, {dateStyle: "medium", timeStyle: "short"});
}

export function formatDateLabel(value) {
    return new Date(value).toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
    });
}

export function formatTrendAxisLabel(value, periodType) {
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

export function formatComparisonRange(currentValue, previousValue, periodType) {
    const currentLabel = formatComparisonPeriod(currentValue, periodType);
    const previousLabel = formatComparisonPeriod(previousValue, periodType);
    if (currentLabel && previousLabel) {
        return `${currentLabel} vs ${previousLabel}`;
    }
    return currentLabel || previousLabel || "Period unavailable";
}

export function formatComparisonPeriod(value, periodType) {
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

export function formatSyncProgress(syncStatus) {
    if (!syncStatus) {
        return "No sync recorded";
    }
    if (syncStatus.progress_total == null || syncStatus.progress_completed == null) {
        return "Progress unavailable";
    }
    return `${syncStatus.progress_completed} / ${syncStatus.progress_total}`;
}

export function formatDateInput(value) {
    const date = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(date.getTime())) {
        return "";
    }
    return date.toISOString().slice(0, 10);
}

export function formatMonthInput(value) {
    const date = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(date.getTime())) {
        return "";
    }
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    return `${year}-${month}`;
}

export function formatDistanceTick(value) {
    return `${Math.round(value)} km`;
}

export function formatSeriesValue(kind, value) {
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

export function formatTooltipSeriesValue(kind, value) {
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

export function formatPaceMinutes(value) {
    const wholeMinutes = Math.floor(value);
    const seconds = Math.round((value - wholeMinutes) * 60);
    const normalizedMinutes = seconds === 60 ? wholeMinutes + 1 : wholeMinutes;
    const normalizedSeconds = seconds === 60 ? 0 : seconds;
    return `${normalizedMinutes}:${String(normalizedSeconds).padStart(2, "0")}`;
}

export function formatSummaryMetricDisplay(value, kind) {
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

export function formatHeartRateDrift(value) {
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

export function formatPaceField(value) {
    const numericValue = Number(value);
    if (!Number.isFinite(numericValue) || numericValue <= 0) {
        return "";
    }
    return formatPaceMinutes(numericValue);
}

export function parsePaceInput(value) {
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

export function buildProfileFormFromItem(item) {
    return {
        effectiveFrom: item?.effective_from ?? formatDateInput(new Date()),
        aerobicThresholdHeartRate: item?.aet_heart_rate_bpm == null ? "" : String(item.aet_heart_rate_bpm),
        anaerobicThresholdHeartRate: item?.ant_heart_rate_bpm == null ? "" : String(item.ant_heart_rate_bpm),
        aerobicThresholdPace: formatPaceField(item?.aet_pace_min_per_km),
        anaerobicThresholdPace: formatPaceField(item?.ant_pace_min_per_km),
    };
}

export function formatThresholdSnapshotSummary(item) {
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

export function formatSportLabel(value) {
    if (value === "EBikeRide") {
        return "E-Bike";
    }
    return formatLabel(value);
}

export function formatPercentage(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) {
        return "n/a";
    }
    return `${formatNumber(numeric)}%`;
}

export function formatDistanceKm(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) {
        return "n/a";
    }
    return `${formatNumber(numeric)} km`;
}

export function formatBandDistribution(items) {
    return (items ?? [])
        .map((item) => `${item.label} ${formatPercentage(item.share_percent)}`)
        .join(" | ");
}

export function formatClimbingSummary(summary) {
    if (!summary) {
        return "n/a";
    }
    return `Climb ${formatPercentage(summary.climbing_share_percent)} | Flat ${formatPercentage(summary.flat_share_percent)} | Down ${formatPercentage(summary.descending_share_percent)}`;
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
