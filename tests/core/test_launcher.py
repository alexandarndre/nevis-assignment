from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from nevis_search.core.errors import ConflictError
from nevis_search.core.launcher.main import create_app
from nevis_search.core.launcher.schemas import App, HealthCheck, Lifespan, Route, Tag
from nevis_search.core.launcher.utils import combine_lifespans
from nevis_search.search.router import EXAMPLE_HITS
from nevis_search.search.schemas import SEARCH_HITS

ROOT = "http://testserver"


def test_business_endpoints_are_versioned_and_operations_are_named(app: FastAPI) -> None:
    operations = {
        (method.upper(), path): operation["operationId"]
        for path, item in app.openapi()["paths"].items()
        for method, operation in item.items()
    }

    assert operations == {
        ("POST", "/api/v1/clients"): "create_client",
        ("GET", "/api/v1/clients/{id}"): "get_client",
        ("POST", "/api/v1/clients/{id}/documents"): "create_document",
        ("GET", "/api/v1/clients/{id}/documents"): "list_documents",
        ("GET", "/api/v1/documents/{id}"): "get_document",
        ("GET", "/api/v1/documents/{id}/summary"): "get_document_summary",
        ("GET", "/api/v1/search"): "search",
        ("GET", "/healthcheck"): "healthcheck",
    }


def test_every_tag_is_described(app: FastAPI) -> None:
    spec = app.openapi()
    used = {tag for item in spec["paths"].values() for operation in item.values() for tag in operation["tags"]}

    assert used == {tag["name"] for tag in spec["tags"]}
    assert all(tag["description"] != "" for tag in spec["tags"])


def test_search_documents_the_cache_header_and_query_examples(app: FastAPI) -> None:
    search = app.openapi()["paths"]["/api/v1/search"]["get"]
    q = next(parameter for parameter in search["parameters"] if parameter["name"] == "q")

    assert "X-Cache" in search["responses"]["200"]["headers"]
    assert "address proof" in q["schema"]["examples"]


def test_search_response_example_matches_the_schema() -> None:
    assert len(SEARCH_HITS.validate_python(EXAMPLE_HITS)) == len(EXAMPLE_HITS)


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json", "/healthcheck"])
def test_operational_endpoints_are_unversioned(api: TestClient, path: str) -> None:
    assert api.get(f"{ROOT}{path}").status_code == 200


@pytest.mark.parametrize("path", ["/search?q=x", "/clients/00000000-0000-0000-0000-000000000000"])
def test_unversioned_business_paths_do_not_exist(api: TestClient, path: str) -> None:
    assert api.get(f"{ROOT}{path}").status_code == 404


async def failing_check() -> None:
    raise ConnectionError("postgres unreachable")


def bare_app(*checks: HealthCheck) -> FastAPI:
    router = APIRouter()

    @router.get("/conflict")
    async def conflict() -> None:
        raise ConflictError("already there")

    return create_app(
        App(
            title="t",
            version="0",
            description="d",
            api_prefix="/api/v1",
            routes=[Route(router=router, prefix="/things", tag=Tag(name="things", description="Things."))],
            healthchecks=list(checks),
        )
    )


def test_healthcheck_is_503_naming_the_failing_dependency() -> None:
    with TestClient(bare_app(failing_check)) as client:
        response = client.get("/healthcheck")

    assert response.status_code == 503
    assert response.json() == {"detail": "ConnectionError: postgres unreachable"}


def test_healthcheck_without_failures_is_ok() -> None:
    with TestClient(bare_app()) as client:
        assert client.get("/healthcheck").json() == {"status": "ok"}


def test_service_errors_map_to_their_status_code() -> None:
    with TestClient(bare_app()) as client:
        response = client.get("/api/v1/things/conflict")

    assert response.status_code == 409
    assert response.json() == {"detail": "already there"}


async def test_lifespans_enter_in_order_and_exit_in_reverse() -> None:
    events: list[str] = []

    def recording(name: str) -> Lifespan:
        @asynccontextmanager
        async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
            events.append(f"enter {name}")
            yield
            events.append(f"exit {name}")

        return lifespan

    async with combine_lifespans(recording("db"), recording("cache"))(FastAPI()):
        events.append("serving")

    assert events == ["enter db", "enter cache", "serving", "exit cache", "exit db"]
