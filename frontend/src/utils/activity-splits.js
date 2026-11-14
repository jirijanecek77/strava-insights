import {downsampleChartData} from "./data";

const finite = (value) => typeof value === "number" && Number.isFinite(value);
const kilometers = (meters) => Math.round(meters * 1000) / 1000000;

export function splitAtDistance(laps, distanceKm) {
    if (!finite(distanceKm)) return null;
    const distance = distanceKm * 1000;
    const visible = laps.filter((lap) => lap.end_distance_meters > lap.start_distance_meters);
    return visible.find((lap, index) => distance + 1e-7 >= lap.start_distance_meters
        && (distance < lap.end_distance_meters - 1e-7
            || (index === visible.length - 1 && Math.abs(distance - lap.end_distance_meters) < 1e-7))) ?? null;
}

export function closestSplitStreamIndex(distances, distanceKm) {
    if (!finite(distanceKm)) return -1;
    let best = -1;
    let difference = Infinity;
    distances.forEach((value, index) => {
        if (finite(value) && Math.abs(value - distanceKm) < difference) {
            difference = Math.abs(value - distanceKm);
            best = index;
        }
    });
    return best;
}

export function calculateSplitElevation(lap, distances, altitudes) {
    if (!lap || !finite(lap.start_distance_meters) || !finite(lap.end_distance_meters)
        || lap.end_distance_meters <= lap.start_distance_meters) return null;
    let ascent = 0;
    let descent = 0;
    let hasElevation = false;
    for (let index = 1; index < distances.length; index += 1) {
        const start = distances[index - 1] * 1000;
        const end = distances[index] * 1000;
        const previous = altitudes[index - 1];
        const current = altitudes[index];
        if (!finite(distances[index - 1]) || !finite(distances[index]) || end <= start
            || !finite(previous) || !finite(current)) continue;
        const overlap = Math.min(end, lap.end_distance_meters) - Math.max(start, lap.start_distance_meters);
        if (overlap <= 0) continue;
        // Interpolate the part of each source segment inside the lap, without bridging missing samples.
        const change = (current - previous) * overlap / (end - start);
        ascent += Math.max(0, change);
        descent += Math.max(0, -change);
        hasElevation = true;
    }
    return hasElevation ? {ascent, descent} : null;
}

export function buildSplitChartData(laps, distances, altitudes, isRun) {
    const visible = laps.filter((lap) => lap.end_distance_meters > lap.start_distance_meters);
    if (!visible.length) return [];
    const first = kilometers(visible[0].start_distance_meters);
    const last = kilometers(visible.at(-1).end_distance_meters);
    const samples = distances.map((distance, index) => ({distance, altitude: finite(altitudes[index]) ? altitudes[index] : null}))
        .filter((point) => finite(point.distance) && point.distance >= first && point.distance <= last);
    // Sample elevation only. Preserve every exact lap boundary, including short intervals.
    const nodes = new Set([first, last, ...downsampleChartData(samples, null, 240).map((point) => point.distance)]);
    visible.forEach((lap) => {
        nodes.add(kilometers(lap.start_distance_meters));
        nodes.add(kilometers(lap.end_distance_meters));
    });
    function point(lap, distance) {
        const metric = isRun ? lap?.average_pace_seconds_per_km : lap?.average_speed_kph;
        const index = closestSplitStreamIndex(distances, distance);
        return {
            distance,
            metric: finite(metric) && metric > 0 ? (isRun ? metric / 60 : metric) : null,
            altitude: index >= 0 && finite(altitudes[index]) ? altitudes[index] : null,
        };
    }
    return [...nodes].sort((a, b) => a - b).flatMap((distance) => {
        const lap = splitAtDistance(visible, distance);
        const ending = visible.find((candidate) => kilometers(candidate.end_distance_meters) === distance);
        // Both sides of a boundary matter: a null next lap must not erase the preceding lap's final segment.
        return ending && ending !== lap ? [point(ending, distance), point(lap, distance)] : [point(lap, distance)];
    });
}
