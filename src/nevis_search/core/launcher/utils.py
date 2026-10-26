from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from fastapi.routing import APIRoute

from nevis_search.core.launcher.schemas import Lifespan


def combine_lifespans(*lifespans: Lifespan) -> Lifespan:
    @asynccontextmanager
    async def combined(app: FastAPI) -> AsyncGenerator[None]:
        async with AsyncExitStack() as stack:
            for lifespan in lifespans:
                await stack.enter_async_context(lifespan(app))
            yield

    return combined


def operation_id(route: APIRoute) -> str:
    return route.name
