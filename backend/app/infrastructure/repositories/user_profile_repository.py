from sqlalchemy.orm import Session

from app.infrastructure.db.models.user_profile import UserProfile


class UserProfileRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_for_user(self, user_id: int) -> UserProfile | None:
        return self.session.query(UserProfile).filter(UserProfile.user_id == user_id).one_or_none()

    def upsert_for_user(
        self,
        *,
        user_id: int,
        aet_heart_rate_bpm,
        ant_heart_rate_bpm,
        aet_pace_min_per_km,
        ant_pace_min_per_km,
    ) -> UserProfile:
        profile = self.get_for_user(user_id)
        if profile is None:
            profile = UserProfile(
                user_id=user_id,
                aet_heart_rate_bpm=aet_heart_rate_bpm,
                ant_heart_rate_bpm=ant_heart_rate_bpm,
                aet_pace_min_per_km=aet_pace_min_per_km,
                ant_pace_min_per_km=ant_pace_min_per_km,
            )
            self.session.add(profile)
        else:
            profile.aet_heart_rate_bpm = aet_heart_rate_bpm
            profile.ant_heart_rate_bpm = ant_heart_rate_bpm
            profile.aet_pace_min_per_km = aet_pace_min_per_km
            profile.ant_pace_min_per_km = ant_pace_min_per_km
        self.session.flush()
        return profile
