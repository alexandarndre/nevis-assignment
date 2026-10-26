import hashlib

from redis.asyncio import Redis

_VERSION = "data-version"


class Cache:
    def __init__(self, redis: Redis, prefix: str) -> None:
        self.redis = redis
        self._prefix = prefix

    def key(self, namespace: str, *parts: str) -> str:
        return f"{self._prefix}:{namespace}:{hashlib.sha256('\x00'.join(parts).encode()).hexdigest()}"

    async def get(self, key: str) -> bytes | None:
        value = await self.redis.get(key)
        assert not isinstance(value, str)
        return value

    async def set(self, key: str, value: bytes, ttl_seconds: int) -> None:
        await self.redis.set(key, value, ex=ttl_seconds)

    async def data_version(self) -> int:
        value = await self.get(f"{self._prefix}:{_VERSION}")
        return 0 if value is None else int(value)

    async def bump_data_version(self) -> None:
        await self.redis.incr(f"{self._prefix}:{_VERSION}")
