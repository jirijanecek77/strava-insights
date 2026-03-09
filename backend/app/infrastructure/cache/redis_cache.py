from collections.abc import Iterable

from redis import Redis

from app.core.config import settings


def build_redis_client() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


class RedisCache:
    def __init__(self, client: Redis | None = None) -> None:
        self.client = client or build_redis_client()

    def delete_many(self, keys: Iterable[str]) -> int:
        key_list = [key for key in keys if key]
        if not key_list:
            return 0
        return int(self.client.delete(*key_list))

    def delete_pattern(self, pattern: str) -> int:
        keys = list(self.client.scan_iter(match=pattern))
        return self.delete_many(keys)
