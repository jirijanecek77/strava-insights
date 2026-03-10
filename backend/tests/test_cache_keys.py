from app.infrastructure.cache.keys import CacheKeys


def test_cache_keys_build_user_scoped_namespaces() -> None:
    assert CacheKeys.user_prefix(7) == "strava_insights:user:7"
    assert CacheKeys.user_pattern(7) == "strava_insights:user:7:*"
    assert CacheKeys.dashboard(7) == "strava_insights:user:7:dashboard"
    assert CacheKeys.activity_list(7) == "strava_insights:user:7:activities"
