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
        birthday,
        speed_max,
        max_heart_rate_override,
    ) -> UserProfile:
        profile = self.get_for_user(user_id)
        if profile is None:
            profile = UserProfile(
                user_id=user_id,
                birthday=birthday,
                speed_max=speed_max,
                max_heart_rate_override=max_heart_rate_override,
            )
            self.session.add(profile)
        else:
            profile.birthday = birthday
            profile.speed_max = speed_max
            profile.max_heart_rate_override = max_heart_rate_override
        self.session.flush()
        return profile
