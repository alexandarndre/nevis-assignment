from collections.abc import Sequence

from fastapi import APIRouter

from nevis_search.core.errors import UnavailableError
from nevis_search.core.healthcheck.schemas import HealthOut
from nevis_search.core.launcher.schemas import HealthCheck, Tag

HEALTH_TAG = Tag(name="health", description="Readiness of the service's dependencies; 503 names the first failing one.")


def healthcheck_router(checks: Sequence[HealthCheck]) -> APIRouter:
    router = APIRouter(tags=[HEALTH_TAG.name])

    @router.get(
        "/healthcheck",
        name="healthcheck",
        summary="Readiness of the database and the cache",
        responses=UnavailableError.documented("A dependency is unreachable"),
    )
    async def healthcheck() -> HealthOut:
        try:
            for check in checks:
                await check()
        except Exception as exc:
            raise UnavailableError(f"{type(exc).__name__}: {exc}") from exc
        return HealthOut(status="ok")

    return router
