from redis.asyncio import Redis

from nevis_search.core.launcher.schemas import HealthCheck


def redis_check(url: str) -> HealthCheck:
    async def check() -> None:
        redis = Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
        try:
            await redis.ping()
        finally:
            await redis.aclose()

    return check
