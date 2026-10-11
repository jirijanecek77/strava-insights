from datetime import date

from sqlalchemy.orm import Session

from app.infrastructure.db.models.coaching import (
    ActivityCoachingNote,
    PeriodCoachingSummary,
)


class CoachingRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_activity_note(
        self, user_id: int, activity_id: int
    ) -> ActivityCoachingNote | None:
        return (
            self.session.query(ActivityCoachingNote)
            .filter(
                ActivityCoachingNote.user_id == user_id,
                ActivityCoachingNote.activity_id == activity_id,
            )
            .one_or_none()
        )

    def list_period_summaries(
        self, user_id: int, *, date_from: date, date_to: date
    ) -> list[PeriodCoachingSummary]:
        return (
            self.session.query(PeriodCoachingSummary)
            .filter(
                PeriodCoachingSummary.user_id == user_id,
                PeriodCoachingSummary.period_start >= date_from,
                PeriodCoachingSummary.period_start <= date_to,
            )
            .order_by(
                PeriodCoachingSummary.period_type.asc(),
                PeriodCoachingSummary.period_start.asc(),
            )
            .all()
        )
