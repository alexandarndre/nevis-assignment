from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from nevis_search.summary.depends import get_summarizer


@asynccontextmanager
async def summary_lifespan(_: FastAPI) -> AsyncGenerator[None]:
    get_summarizer()
    yield
    get_summarizer.cache_clear()
