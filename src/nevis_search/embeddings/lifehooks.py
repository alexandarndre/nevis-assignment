from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from nevis_search.core.launcher.schemas import Lifespan
from nevis_search.embeddings.service import load_embedder
from nevis_search.embeddings.settings import EmbeddingSettings


def embeddings_lifespan(settings: EmbeddingSettings) -> Lifespan:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        load_embedder(settings)
        yield

    return lifespan
