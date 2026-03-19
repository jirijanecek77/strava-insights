import logging

from app.cache import RedisCache
from app.cache_keys import CacheKeys


logger = logging.getLogger(__name__)


class UserCacheInvalidator:
    def __init__(self, cache: RedisCache | None = None) -> None:
        self.cache = cache or RedisCache()

    def invalidate_user(self, user_id: int) -> int:
        deleted_count = self.cache.delete_pattern(CacheKeys.user_pattern(user_id))
        logger.info("Invalidated cache entries for user.", extra={"user.id": user_id, "deleted_keys": deleted_count})
        return deleted_count
