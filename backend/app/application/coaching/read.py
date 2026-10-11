from datetime import date, timedelta

from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.domain.schemas.coaching import (
    ActivityCoachingResponse,
    PeriodCoachingItem,
    PeriodCoachingResponse,
)
from app.infrastructure.db.models.coaching import (
    ActivityCoachingNote,
    PeriodCoachingSummary,
)
from app.infrastructure.repositories.coaching_repository import CoachingRepository


def to_activity_coaching_response(
    note: ActivityCoachingNote | None,
) -> ActivityCoachingResponse | None:
    if note is None:
        return None
    # Earlier text stays readable while a regeneration is pending.
    has_text = note.description is not None
    return ActivityCoachingResponse(
        status="ready" if has_text else note.status,  # type: ignore[arg-type]
        description=note.description,
        summary=note.summary,
        recommendation=note.recommendation,
        model=note.model,
        generated_at=note.generated_at,
    )


def period_end(period_type: str, period_start: date) -> date:
    """Return the inclusive last day of a week or month period."""
    if period_type == "week":
        return period_start + timedelta(days=6)
    next_month = (period_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    return next_month - timedelta(days=1)


class CoachingReadService:
    def __init__(self, db_session: Session = Depends(get_db_session)) -> None:
        self.coaching = CoachingRepository(db_session)

    def list_periods(
        self, user_id: int, *, date_from: date, date_to: date
    ) -> PeriodCoachingResponse:
        # Include periods that started before the range but overlap it, e.g. a week that began last month.
        query_from = min(date_from.replace(day=1), date_from - timedelta(days=6))
        items = [
            self._to_period_item(summary)
            for summary in self.coaching.list_period_summaries(
                user_id, date_from=query_from, date_to=date_to
            )
        ]
        return PeriodCoachingResponse(
            items=[
                item
                for item in items
                if item.period_end >= date_from and item.period_start <= date_to
            ]
        )

    @staticmethod
    def _to_period_item(summary: PeriodCoachingSummary) -> PeriodCoachingItem:
        has_text = summary.summary is not None
        return PeriodCoachingItem(
            period_type=summary.period_type,  # type: ignore[arg-type]
            period_start=summary.period_start,
            period_end=period_end(summary.period_type, summary.period_start),
            # A period with earlier text stays readable while a refresh is pending.
            status="ready" if has_text else summary.status,  # type: ignore[arg-type]
            summary=summary.summary,
            recommendation=summary.recommendation,
            is_final=summary.is_final,
            model=summary.model,
            generated_at=summary.generated_at,
        )
