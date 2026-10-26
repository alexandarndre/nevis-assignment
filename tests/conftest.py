from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field
from redis import Redis
from sqlalchemy import Engine, create_engine, text
from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.redis import RedisContainer

from nevis_search.app import build_app
from nevis_search.clients.schemas import ClientOut
from nevis_search.documents.schemas import DocumentOut
from nevis_search.seed import SEED
from nevis_search.settings import get_settings

ROOT = Path(__file__).parents[1]


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    with PostgresContainer("pgvector/pgvector:0.8.1-pg17", driver="psycopg") as postgres:
        yield postgres.get_connection_url()


@pytest.fixture(scope="session")
def redis_url() -> Iterator[str]:
    with RedisContainer("redis:7.4-alpine") as redis:
        yield f"redis://{redis.get_container_host_ip()}:{redis.get_exposed_port(6379)}/0"


@pytest.fixture(scope="session")
def db(database_url: str) -> Iterator[Engine]:
    engine = create_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def app(database_url: str, redis_url: str) -> Iterator[FastAPI]:
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("DATABASE_URL", database_url)
        patch.setenv("REDIS_URL", redis_url)
        patch.delenv("ANTHROPIC_API_KEY", raising=False)
        get_settings.cache_clear()
        command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
        yield build_app()
    get_settings.cache_clear()


@pytest.fixture(scope="session")
def api(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, base_url="http://testserver/api/v1") as client:
        yield client


def reset(db: Engine, redis_url: str) -> None:
    with db.begin() as conn:
        conn.execute(text("TRUNCATE clients CASCADE"))
    Redis.from_url(redis_url).flushdb()


@pytest.fixture
def client(app: FastAPI, api: TestClient, db: Engine, redis_url: str) -> Iterator[TestClient]:
    reset(db, redis_url)
    yield api
    app.dependency_overrides.clear()


class Seeded(BaseModel):
    clients: dict[str, ClientOut] = Field(default_factory=dict)
    documents: dict[str, DocumentOut] = Field(default_factory=dict)


def seed(api: TestClient) -> Seeded:
    seeded = Seeded()
    for entry in SEED:
        response = api.post("/clients", json=entry.client.model_dump(mode="json"))
        assert response.status_code == 201, response.text
        created = ClientOut.model_validate_json(response.content)
        seeded.clients[created.email] = created
        for document in entry.documents:
            response = api.post(f"/clients/{created.id}/documents", json=document.model_dump(mode="json"))
            assert response.status_code == 201, response.text
            stored = DocumentOut.model_validate_json(response.content)
            seeded.documents[stored.title] = stored
    return seeded


@pytest.fixture(scope="module")
def seeded(api: TestClient, db: Engine, redis_url: str) -> Seeded:
    reset(db, redis_url)
    return seed(api)
