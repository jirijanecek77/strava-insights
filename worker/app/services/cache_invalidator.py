from app.cache import RedisCache
from app.cache_keys import CacheKeys


class UserCacheInvalidator:
    def __init__(self, cache: RedisCache | None = None) -> None:
        self.cache = cache or RedisCache()

    def invalidate_user(self, user_id: int) -> int:
        return self.cache.delete_pattern(CacheKeys.user_pattern(user_id))
