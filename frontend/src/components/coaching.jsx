import {Sparkles} from "lucide-react";

import {getIsoWeek} from "../utils/data";
import {EmptyState} from "./common";

export function ActivityCoachingCard({coaching}) {
    if (!coaching) {
        return null;
    }
    return (
        <section className="detail-card coaching-card" aria-label="AI coach">
            <CoachingHeading label="AI Coach" model={coaching.model}/>
            {coaching.status === "ready" ? (
                <>
                    {coaching.summary ? <p className="coaching-summary">{coaching.summary}</p> : null}
                    <CoachingParagraphs text={coaching.description}/>
                    <CoachingNext label="Next session" text={coaching.recommendation}/>
                </>
            ) : (
                <EmptyState compact text={pendingText(coaching.status, "Your coaching notes for this activity")}/>
            )}
        </section>
    );
}

export function PeriodCoachingPanel({calendarMonth, items}) {
    const monthStart = monthStartKey(calendarMonth);
    const month = items.find((item) => item.period_type === "month" && item.period_start === monthStart);
    const weeks = items
        .filter((item) => item.period_type === "week")
        .sort((left, right) => right.period_start.localeCompare(left.period_start));
    if (!month && !weeks.length) {
        return null;
    }
    return (
        <section className="coaching-periods" aria-label="AI coach reviews">
            <CoachingHeading label="AI Coach Reviews"/>
            <div className="coaching-period-grid">
                {month ? (
                    <PeriodCoachingItem
                        item={month}
                        title={calendarMonth.toLocaleDateString(undefined, {month: "long", year: "numeric"})}
                    />
                ) : null}
                {weeks.map((week) => (
                    <PeriodCoachingItem key={week.period_start} item={week} title={formatWeekTitle(week)}/>
                ))}
            </div>
        </section>
    );
}

function PeriodCoachingItem({item, title}) {
    const nextLabel = item.period_type === "week"
        ? (item.is_final ? "Next week" : "Rest of the week")
        : (item.is_final ? "Next month" : "Rest of the month");
    return (
        <article className="coaching-period">
            <div className="coaching-period-heading">
                <h3>{title}</h3>
                {item.status === "ready" && !item.is_final ? <span className="coaching-badge">In progress</span> : null}
            </div>
            {item.status === "ready" ? (
                <>
                    <ThresholdTotals metrics={item.metrics}/>
                    <CoachingParagraphs text={item.summary}/>
                    <CoachingNext label={nextLabel} text={item.recommendation}/>
                </>
            ) : (
                <EmptyState compact text={pendingText(item.status, "This review")}/>
            )}
        </article>
    );
}

function ThresholdTotals({metrics}) {
    const sports = Object.entries(metrics?.hr_bands_by_sport || {});
    if (!sports.length) return null;
    const labels = {below_aet: "Below AeT", between_aet_ant: "AeT to below AnT", above_ant: "At/above AnT"};
    const duration = (value) => {
        if (value == null) return "Unavailable";
        const seconds = Math.round(value);
        return `${Math.floor(seconds / 3600)}:${String(Math.floor(seconds / 60) % 60).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
    };
    return <div className="coaching-band-totals">
        {sports.map(([sport, data]) => <div key={sport}>
            <table aria-label={`${sport} heart-rate threshold totals`}>
                <caption>{sport} · Measured HR bands</caption>
                <thead><tr><th scope="col">Intensity</th><th scope="col">Time</th><th scope="col">Distance</th></tr></thead>
                <tbody>{Object.entries(labels).map(([key, label]) => <tr key={key}>
                    <th scope="row">{label}</th>
                    <td>{duration(data.bands[key].time_s)}</td>
                    <td>{data.bands[key].distance_m == null ? "Unavailable" : `${(data.bands[key].distance_m / 1000).toFixed(2)} km`}</td>
                </tr>)}</tbody>
            </table>
            <p className="coaching-text">Unclassified: {duration(data.coverage.unknown_time_s)} · {(data.coverage.unknown_distance_m / 1000).toFixed(2)} km.
                {data.threshold_definitions?.length > 1 ? " Threshold definitions changed during this period." : ""}
                {sport !== "Run" ? " Uses your configured HR thresholds." : ""}
            </p>
            {data.limitations?.filter((text) => text.includes("exceeds")).map((text) => <p className="coaching-text" key={text}>{text}</p>)}
        </div>)}
    </div>;
}

function CoachingHeading({label, model}) {
    return (
        <div className="coaching-heading">
            <p className="eyebrow"><Sparkles aria-hidden="true" size={12}/> {label}</p>
            {model ? <span className="coaching-model">{model}</span> : null}
        </div>
    );
}

function CoachingParagraphs({text}) {
    if (!text) {
        return null;
    }
    return text
        .split(/\n\s*\n/)
        .map((paragraph) => paragraph.trim())
        .filter(Boolean)
        .map((paragraph, index) => <p className="coaching-text" key={index}>{paragraph}</p>);
}

function CoachingNext({label, text}) {
    if (!text) {
        return null;
    }
    return (
        <div className="coaching-next">
            <strong>{label}</strong>
            <p>{text}</p>
        </div>
    );
}

function pendingText(status, subject) {
    if (status === "failed") {
        return `${subject} could not be generated.`;
    }
    return `${subject} will be written shortly.`;
}

function formatWeekTitle(week) {
    const start = parseDateKey(week.period_start);
    const end = parseDateKey(week.period_end);
    const format = (value) => value.toLocaleDateString(undefined, {month: "short", day: "numeric"});
    return `Week ${getIsoWeek(start)} · ${format(start)} – ${format(end)}`;
}

function parseDateKey(value) {
    const [year, month, day] = value.split("-").map(Number);
    return new Date(year, month - 1, day);
}

function monthStartKey(value) {
    const month = String(value.getMonth() + 1).padStart(2, "0");
    return `${value.getFullYear()}-${month}-01`;
}
