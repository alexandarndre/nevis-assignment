from redis.asyncio import Redis

from nevis_search.core.cache.base import Cache


def test_cache_keys_are_stable_namespaced_and_unambiguous() -> None:
    cache = Cache(Redis.from_url("redis://localhost:1"), "nevis")

    assert cache.key("search", "q") == cache.key("search", "q")
    assert cache.key("search", "q").startswith("nevis:search:")
    assert cache.key("search", "q") != cache.key("summary", "q")
    assert cache.key("summary", "a", "bc") != cache.key("summary", "ab", "c")
