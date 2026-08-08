class CacheKeys:
    USER_PREFIX = "intervals_insights:user"

    @classmethod
    def user_pattern(cls, user_id: int) -> str:
        return f"{cls.USER_PREFIX}:{user_id}:*"
