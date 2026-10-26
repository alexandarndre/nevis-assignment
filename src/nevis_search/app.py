from fastapi import FastAPI

from nevis_search.clients.router import router as clients_router
from nevis_search.core.cache.healthcheck import redis_check
from nevis_search.core.cache.lifehooks import cache_lifespan
from nevis_search.core.db.healthcheck import postgres_check
from nevis_search.core.db.lifehooks import db_lifespan
from nevis_search.core.launcher.main import create_app, run
from nevis_search.core.launcher.schemas import App, Route, Tag
from nevis_search.documents.router import router as documents_router
from nevis_search.embeddings.lifehooks import embeddings_lifespan
from nevis_search.search.lifehooks import search_lifespan
from nevis_search.search.router import router as search_router
from nevis_search.settings import get_settings
from nevis_search.summary.lifehooks import summary_lifespan
from nevis_search.summary.router import router as summary_router

DESCRIPTION = """
Search API for advisors across clients and their documents.

* **Clients** are matched on name, email and description, typo tolerant.
* **Documents** are matched on keywords, domain synonyms and meaning.
* **Summaries** come from Claude when an API key is configured, extractive otherwise.

Business endpoints are versioned under `/api/v1`. A breaking change ships as `/api/v2` next to v1;
additive changes (new fields, endpoints or optional parameters) stay in v1. `/healthcheck` and the
documentation are unversioned.
"""

CLIENTS = Tag(name="clients", description="Advisor clients. Emails are unique regardless of case.")
DOCUMENTS = Tag(
    name="documents",
    description="Client documents. Uploads are split into passages and indexed for keyword and semantic search.",
)
SEARCH = Tag(name="search", description="One query across clients and their documents.")


def build_app() -> FastAPI:
    settings = get_settings()
    return create_app(
        App(
            title=settings.PROJECT_NAME,
            version=settings.PROJECT_VERSION,
            description=DESCRIPTION,
            api_prefix="/api/v1",
            routes=[
                Route(router=clients_router, prefix="/clients", tag=CLIENTS),
                Route(router=documents_router, prefix="", tag=DOCUMENTS),
                Route(router=summary_router, prefix="/documents", tag=DOCUMENTS),
                Route(router=search_router, prefix="/search", tag=SEARCH),
            ],
            healthchecks=[postgres_check(settings.DATABASE_URL), redis_check(settings.REDIS_URL)],
            lifespans=[
                embeddings_lifespan(settings),
                search_lifespan(settings),
                summary_lifespan,
                db_lifespan(settings.DATABASE_URL),
                cache_lifespan(settings.REDIS_URL, settings.REDIS_KEY_PREFIX),
            ],
        )
    )


def launch() -> None:
    run("nevis_search.app:build_app", get_settings())
