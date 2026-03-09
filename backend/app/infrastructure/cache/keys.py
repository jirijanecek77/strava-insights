class CacheKeys:
    USER_PREFIX = "strava_insights:user"

    @classmethod
    def user_prefix(cls, user_id: int) -> str:
        return f"{cls.USER_PREFIX}:{user_id}"

    @classmethod
    def user_pattern(cls, user_id: int) -> str:
        return f"{cls.user_prefix(user_id)}:*"

    @classmethod
    def dashboard(cls, user_id: int) -> str:
        return f"{cls.user_prefix(user_id)}:dashboard"

    @classmethod
    def activity_list(cls, user_id: int) -> str:
        return f"{cls.user_prefix(user_id)}:activities"
