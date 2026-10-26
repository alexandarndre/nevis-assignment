from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from functools import lru_cache

from fastapi import FastAPI
from redis.asyncio import Redis

from nevis_search.core.cache.base import Cache
from nevis_search.core.launcher.schemas import Lifespan


@lru_cache
def get_cache(url: str, prefix: str) -> Cache:
    return Cache(Redis.from_url(url), prefix)


def cache_lifespan(url: str, prefix: str) -> Lifespan:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        yield
        await get_cache(url, prefix).redis.aclose()
        get_cache.cache_clear()

    return lifespan
