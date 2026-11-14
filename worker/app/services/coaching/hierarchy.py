"""Build reviews exclusively from persisted results of the level below."""

from collections import defaultdict
from datetime import date, timedelta
from typing import Protocol

from app.services.coaching.contracts import (
    ActivityEvaluation,
    ActivityFacts,
    DailyFacts,
    HierarchyFacts,
    PeriodEvaluation,
)
from app.services.coaching.evidence import (
    aggregate_evidence,
    compare_performance,
    fingerprint,
)
from app.services.coaching.periods import (
    PeriodContext,
    period_bounds,
    period_start_for,
    previous_period_start,
)
from app.services.coaching.prompts import PROMPT_VERSION

PREVIOUS_PERIODS = 3


class HierarchyRepository(Protocol):
    def list_activity_evaluations(
            self, *, user_id: int, start: date, end: date
    ) -> list[ActivityEvaluation]: ...

    def list_period_evaluations(
            self, *, user_id: int, period_type: str, start: date, end: date
    ) -> list[PeriodEvaluation]: ...


class PeriodContextBuilder:
    def __init__(self, repository: HierarchyRepository):
        self.repository = repository

    def build(
            self, *, user_id: int, period_type: str, period_start: date, today: date
    ) -> PeriodContext:
        start, end = period_bounds(period_type, period_start)
        current_end = max(start, min(end, today + timedelta(days=1)))
        previous_start, previous_end = period_bounds(
            period_type, previous_period_start(period_type, start)
        )
        comparison_end = (
            min(previous_end, previous_start + (current_end - start))
            if end > today
            else previous_end
        )
        context_start = start
        for _ in range(PREVIOUS_PERIODS):
            context_start = previous_period_start(period_type, context_start)
        surrounding = self._periods(user_id, period_type, context_start, start)
        revisions = {}

        if period_type == "week":
            evaluations = [
                ActivityEvaluation.model_validate(row)
                for row in self.repository.list_activity_evaluations(
                    user_id=user_id,
                    start=start,
                    end=current_end,
                )
            ]
            revisions = {
                str(row.facts.activity_id): row.revision for row in evaluations
            }
            days = self._days((row.facts for row in evaluations), revisions)
            digests = [
                {
                    "activity_id": row.facts.activity_id,
                    "date": str(row.facts.date),
                    "sport": row.facts.sport,
                    "summary": row.summary,
                }
                for row in evaluations
            ]
            pending = any(
                row.status in {"pending", "generating"} for row in evaluations
            )
            ready = any(row.summary for row in evaluations)
            previous_days = self._stored_days(surrounding, previous_start, previous_end)
            covered_days = (current_end - start).days
            previous_covered_days = self._covered_days(
                surrounding, previous_start, comparison_end
            )
            interpretation_coverage = {
                "activities": len(evaluations),
                "ready_notes": sum(bool(row.summary) for row in evaluations),
                "prepared_facts": sum(row.facts_ready for row in evaluations),
            }
        else:
            weeks = self._periods(
                user_id, "week", period_start_for("week", previous_start), current_end
            )
            own_weeks = [
                week
                for week in weeks
                if period_bounds("week", week.period_start)[1] > start
            ]
            days = self._stored_days(own_weeks, start, current_end)
            previous_days = self._stored_days(weeks, previous_start, previous_end)
            covered_days = self._covered_days(own_weeks, start, current_end)
            previous_covered_days = self._covered_days(
                weeks, previous_start, comparison_end
            )
            digests = [
                self._week_digest(week, start, current_end) for week in own_weeks
            ]
            revisions = {
                str(week.period_start): self._revision(week) for week in own_weeks
            }
            pending = any(
                week.status in {"pending", "generating"}
                or self._hierarchy(week) is None
                for week in own_weeks
            )
            ready = any(
                week.summary and self._hierarchy(week) is not None for week in own_weeks
            )
            interpretation_coverage = {
                "weeks": len(own_weeks),
                "ready_weeks": sum(bool(week.summary) for week in own_weeks),
            }

        facts = self._facts(days)
        old_facts = self._facts(
            [day for day in previous_days if day.date < comparison_end]
        )
        previous_full = self._facts(previous_days)
        bands, old_bands = aggregate_evidence(facts), aggregate_evidence(old_facts)
        _add_percentages(bands)
        _add_percentages(old_bands)
        totals, previous_totals = _totals(facts), _totals(old_facts)
        context = {
            "period_type": period_type,
            "period_start": str(start),
            "period_end": str(end - timedelta(days=1)),
            "in_progress": end > today,
            "comparison_windows": {
                "current_start": str(start),
                "current_end": str(current_end - timedelta(days=1)),
                "previous_start": str(previous_start),
                "previous_end": str(comparison_end - timedelta(days=1)),
                "current_days": (current_end - start).days,
                "previous_days": (comparison_end - previous_start).days,
            },
            "totals_by_sport": totals,
            "previous_period_totals_by_sport": previous_totals,
            "previous_full_period_totals_by_sport": _totals(previous_full),
            "hr_bands_by_sport": bands,
            "previous_hr_bands_by_sport": old_bands,
            "distance_comparison_by_sport": _distance_changes(totals, previous_totals),
            "hr_band_distance_comparison_by_sport": _band_changes(bands, old_bands),
            "performance_comparison": compare_performance(facts, old_facts),
            "training_days": len(days),
            "running_days": sum(
                any(row.sport == "Run" for row in day.activities) for day in days
            ),
            "rest_days": (
                max(0, covered_days - len(days))
                if covered_days == (current_end - start).days
                else None
            ),
            "date_coverage": {
                "covered_days": covered_days,
                "period_days": (current_end - start).days,
                "previous_covered_days": previous_covered_days,
                "previous_period_days": (comparison_end - previous_start).days,
            },
            "interpretation_coverage": interpretation_coverage,
            "previous_reviews": [
                self._digest(row) for row in surrounding if row.summary
            ][-PREVIOUS_PERIODS:],
            "activities" if period_type == "week" else "weeks": digests,
            "limitations": [
                "Expected workout stimulus is distinct from demonstrated fitness improvement.",
                "Whole-week narratives can include days outside this calendar month; only date-clipped numeric evidence belongs to this month.",
                "Higher training volume alone does not establish improved endurance or pace.",
            ],
        }
        hierarchy = HierarchyFacts(
            as_of=current_end - timedelta(days=1), days=days, input_revisions=revisions
        )
        metrics = {
            key: value
            for key, value in context.items()
            if key not in {"activities", "weeks", "previous_reviews"}
        }
        metrics["hierarchy"] = hierarchy.model_dump(mode="json")
        source_hash = fingerprint(
            [
                PROMPT_VERSION,
                context,
                hierarchy.model_dump(mode="json"),
                [self._revision(row) for row in surrounding],
            ]
        )
        return PeriodContext(
            context, source_hash, end <= today, pending, ready, metrics
        )

    def _periods(self, user_id, period_type, start, end):
        return sorted(
            (
                PeriodEvaluation.model_validate(row)
                for row in self.repository.list_period_evaluations(
                user_id=user_id, period_type=period_type, start=start, end=end
            )
            ),
            key=lambda row: row.period_start,
        )

    @staticmethod
    def _days(facts, revisions):
        grouped = defaultdict(list)
        for item in facts:
            grouped[item.date].append(item)
        return [
            DailyFacts(
                date=day,
                activities=sorted(rows, key=lambda row: row.activity_id),
                input_revisions={
                    str(row.activity_id): revisions[str(row.activity_id)]
                    for row in rows
                },
            )
            for day, rows in sorted(grouped.items())
        ]

    @staticmethod
    def _hierarchy(period):
        payload = (period.metrics or {}).get("hierarchy")
        return HierarchyFacts.model_validate(payload) if payload else None

    @classmethod
    def _stored_days(cls, periods, start, end):
        result = {}
        ids = set()
        for period in periods:
            saved = cls._hierarchy(period)
            if saved is None:
                continue
            for day in saved.days:
                if start <= day.date < end:
                    if day.date in result:
                        raise ValueError("Overlapping weekly coaching facts.")
                    for activity in day.activities:
                        if activity.activity_id in ids:
                            raise ValueError(
                                "Duplicate activity in weekly coaching facts."
                            )
                        ids.add(activity.activity_id)
                    result[day.date] = day
        return [result[day] for day in sorted(result)]

    @staticmethod
    def _facts(days):
        return [
            activity.model_dump(mode="json")
            for day in days
            for activity in day.activities
        ]

    @classmethod
    def _covered_days(cls, periods, start, end):
        covered = set()
        for period in periods:
            saved = cls._hierarchy(period)
            if saved is None:
                continue
            day = max(start, period.period_start)
            stop = min(
                end,
                period_bounds("week", period.period_start)[1],
                saved.as_of + timedelta(days=1),
            )
            while day < stop:
                covered.add(day)
                day += timedelta(days=1)
        return len(covered)

    @staticmethod
    def _revision(period):
        return fingerprint(
            [period.source_hash, period.status, period.summary, period.metrics]
        )

    @staticmethod
    def _digest(period):
        metrics = period.metrics or {}
        return {
            "period_start": str(period.period_start),
            "summary": period.summary,
            "is_final": period.is_final,
            "totals_by_sport": metrics.get("totals_by_sport", {}),
        }

    @classmethod
    def _week_digest(cls, week, start, end):
        week_end = period_bounds("week", week.period_start)[1]
        saved = cls._hierarchy(week)
        return {
            **cls._digest(week),
            "period_end": str(week_end - timedelta(days=1)),
            "included_start": str(max(start, week.period_start)),
            "included_end": str(min(end, week_end) - timedelta(days=1)),
            "partial_week": week.period_start < start or week_end > end,
            "as_of": str(saved.as_of) if saved else None,
        }


def _add_percentages(sports):
    for row in sports.values():
        total = sum(value["time_s"] or 0 for value in row["bands"].values())
        for value in row["bands"].values():
            value["time_percent"] = (
                value["time_s"] * 100 / total
                if total and value["time_s"] is not None
                else None
            )


def _totals(facts):
    totals = {}
    for fact in facts:
        row = totals.setdefault(
            fact["sport"], {"activities": 0, "distance_km": 0.0, "moving_seconds": 0.0}
        )
        row["activities"] += 1
        row["distance_km"] += fact["volume"]["distance_m"] / 1000
        row["moving_seconds"] += fact["volume"]["moving_time_s"]
    return totals


def _distance_changes(current, previous):
    result = {}
    for sport in sorted(set(current) | set(previous)):
        now = current.get(sport, {}).get("distance_km", 0) * 1000
        old = previous.get(sport, {}).get("distance_km", 0) * 1000
        result[sport] = {
            "current_distance_m": now,
            "previous_distance_m": old,
            "change_m": now - old,
            "change_pct": (now / old - 1) * 100 if old else None,
        }
    return result


def _band_changes(current, previous):
    result = {}
    for sport in sorted(set(current) | set(previous)):
        result[sport] = {}
        for band in ("below_aet", "between_aet_ant", "above_ant"):
            now = (
                current.get(sport, {}).get("bands", {}).get(band, {}).get("distance_m")
            )
            old = (
                previous.get(sport, {}).get("bands", {}).get(band, {}).get("distance_m")
            )
            result[sport][band] = {
                "current_distance_m": now,
                "previous_distance_m": old,
                "change_m": now - old if now is not None and old is not None else None,
                "change_pct": (
                    (now / old - 1) * 100 if now is not None and old else None
                ),
            }
    return result
