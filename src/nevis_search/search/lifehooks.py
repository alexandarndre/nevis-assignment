from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from nevis_search.core.launcher.schemas import Lifespan
from nevis_search.search.settings import SearchSettings
from nevis_search.search.synonyms import load_synonyms


def search_lifespan(settings: SearchSettings) -> Lifespan:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        load_synonyms(settings.SYNONYMS_PATH)
        yield

    return lifespan
