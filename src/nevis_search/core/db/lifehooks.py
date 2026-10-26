from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from functools import lru_cache

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from nevis_search.core.launcher.schemas import Lifespan


@lru_cache
def get_engine(url: str) -> AsyncEngine:
    return create_async_engine(url, pool_pre_ping=True)


def db_lifespan(url: str) -> Lifespan:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        yield
        await get_engine(url).dispose()
        get_engine.cache_clear()

    return lifespan
