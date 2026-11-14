from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True, slots=True)
class PeriodContext:
    context: dict
    source_hash: str
    is_final: bool
    has_pending_notes: bool
    has_ready_notes: bool
    metrics: dict | None = None


def period_bounds(period_type: str, period_start: date) -> tuple[date, date]:
    if period_type == "week":
        return period_start, period_start + timedelta(days=7)
    if period_type != "month":
        raise ValueError(f"Unsupported coaching period: {period_type}")
    return period_start, (period_start.replace(day=28) + timedelta(days=4)).replace(
        day=1
    )


def period_start_for(period_type: str, day: date) -> date:
    return (
        day - timedelta(days=day.weekday())
        if period_type == "week"
        else day.replace(day=1)
    )


def previous_period_start(period_type: str, period_start: date) -> date:
    if period_type == "week":
        return period_start - timedelta(days=7)
    return (period_start - timedelta(days=1)).replace(day=1)
