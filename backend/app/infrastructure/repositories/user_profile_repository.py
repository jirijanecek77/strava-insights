from datetime import date

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.infrastructure.db.models.user_threshold_profile import UserThresholdProfile


class UserProfileRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_for_user(self, user_id: int) -> list[UserThresholdProfile]:
        return (
            self.session.query(UserThresholdProfile)
            .filter(UserThresholdProfile.user_id == user_id)
            .order_by(UserThresholdProfile.effective_from.desc())
            .all()
        )

    def get_current_for_user(self, user_id: int) -> UserThresholdProfile | None:
        return (
            self.session.query(UserThresholdProfile)
            .filter(UserThresholdProfile.user_id == user_id)
            .order_by(UserThresholdProfile.effective_from.desc())
            .first()
        )

    def get_effective_for_user(self, user_id: int, effective_date: date | None) -> UserThresholdProfile | None:
        if effective_date is None:
            return self.get_current_for_user(user_id)
        return (
            self.session.query(UserThresholdProfile)
            .filter(
                UserThresholdProfile.user_id == user_id,
                UserThresholdProfile.effective_from <= effective_date,
            )
            .order_by(UserThresholdProfile.effective_from.desc())
            .first()
        )

    def upsert_for_user(
        self,
        *,
        user_id: int,
        effective_from,
        aet_heart_rate_bpm,
        ant_heart_rate_bpm,
        aet_pace_min_per_km,
        ant_pace_min_per_km,
    ) -> UserThresholdProfile:
        statement = (
            insert(UserThresholdProfile)
            .values(
                user_id=user_id,
                effective_from=effective_from,
                aet_heart_rate_bpm=aet_heart_rate_bpm,
                ant_heart_rate_bpm=ant_heart_rate_bpm,
                aet_pace_min_per_km=aet_pace_min_per_km,
                ant_pace_min_per_km=ant_pace_min_per_km,
                created_at=func.now(),
                updated_at=func.now(),
            )
            .on_conflict_do_update(
                constraint="uq_user_threshold_profiles_user_date",
                set_={
                    "aet_heart_rate_bpm": aet_heart_rate_bpm,
                    "ant_heart_rate_bpm": ant_heart_rate_bpm,
                    "aet_pace_min_per_km": aet_pace_min_per_km,
                    "ant_pace_min_per_km": ant_pace_min_per_km,
                    "updated_at": func.now(),
                },
            )
            .returning(UserThresholdProfile.id)
        )
        profile_id = self.session.execute(statement).scalar_one()
        self.session.flush()
        return self.session.get(UserThresholdProfile, profile_id)
