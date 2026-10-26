import uvicorn
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse

from nevis_search.core.errors import ErrorOut, ServiceError
from nevis_search.core.healthcheck.handler import HEALTH_TAG, healthcheck_router
from nevis_search.core.launcher.schemas import App
from nevis_search.core.launcher.settings import LauncherSettings
from nevis_search.core.launcher.utils import combine_lifespans, operation_id


def create_app(spec: App) -> FastAPI:
    app = FastAPI(
        title=spec.title,
        version=spec.version,
        description=spec.description,
        openapi_tags=[tag.model_dump() for tag in [*spec.tags(), HEALTH_TAG]],
        generate_unique_id_function=operation_id,
        swagger_ui_parameters=spec.swagger_ui.model_dump(by_alias=True),
        lifespan=combine_lifespans(*spec.lifespans),
    )
    api = APIRouter(prefix=spec.api_prefix)
    for route in spec.routes:
        api.include_router(route.router, prefix=route.prefix, tags=[route.tag.name])
    app.include_router(api)
    app.include_router(healthcheck_router(spec.healthchecks))

    @app.exception_handler(ServiceError)
    async def service_error(_: Request, exc: ServiceError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=ErrorOut(detail=str(exc)).model_dump())

    return app


def run(factory: str, settings: LauncherSettings) -> None:
    uvicorn.run(
        factory,
        factory=True,
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        workers=settings.WORKERS,
        reload=settings.RELOAD,
    )
