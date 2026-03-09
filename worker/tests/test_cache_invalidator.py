from app.services.cache_invalidator import UserCacheInvalidator


class RedisCacheStub:
    def __init__(self) -> None:
        self.patterns: list[str] = []

    def delete_pattern(self, pattern: str) -> int:
        self.patterns.append(pattern)
        return 3


def test_user_cache_invalidator_deletes_user_scoped_pattern() -> None:
    cache = RedisCacheStub()

    deleted = UserCacheInvalidator(cache).invalidate_user(9)

    assert deleted == 3
    assert cache.patterns == ["strava_insights:user:9:*"]
