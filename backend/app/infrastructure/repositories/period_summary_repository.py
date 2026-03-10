from datetime import date

from sqlalchemy.orm import Session

from app.infrastructure.db.models.period_summary import PeriodSummary


class PeriodSummaryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_for_user(
        self,
        user_id: int,
        *,
        period_type: str | None = None,
        sport_type: str | None = None,
    ) -> list[PeriodSummary]:
        query = self.session.query(PeriodSummary).filter(PeriodSummary.user_id == user_id)
        if period_type is not None:
            query = query.filter(PeriodSummary.period_type == period_type)
        if sport_type is not None:
            query = query.filter(PeriodSummary.sport_type == sport_type)
        return query.order_by(PeriodSummary.period_start.asc(), PeriodSummary.sport_type.asc()).all()

    def get_for_period(
        self,
        user_id: int,
        *,
        period_type: str,
        period_start: date,
        sport_type: str | None = None,
    ) -> list[PeriodSummary]:
        query = self.session.query(PeriodSummary).filter(
            PeriodSummary.user_id == user_id,
            PeriodSummary.period_type == period_type,
            PeriodSummary.period_start == period_start,
        )
        if sport_type is not None:
            query = query.filter(PeriodSummary.sport_type == sport_type)
        return query.order_by(PeriodSummary.sport_type.asc()).all()
