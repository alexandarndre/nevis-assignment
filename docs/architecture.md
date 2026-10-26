# Architecture

The repository follows the layout of [FastLoom](https://github.com/aradng/FastLoom), without depending on it. A small in-house framework lives in `core/`, organised by capability. Every business feature is a package with the same set of modules. The service itself is declared in two files, `settings.py` and `app.py`.

```
src/nevis_search/
  settings.py           Settings = GeneralSettings + LauncherSettings + every capability mixin
  app.py                App(...) declaration: routes, healthchecks, lifespans; `launch` entrypoint
  seed.py               demo data loader (`seed` entrypoint, calls the API)
  core/                 framework, no business logic
    launcher/           schemas.py (App, Route, Tag)  main.py (create_app, run)  settings.py  utils.py
    settings/           base.py (project + env-file settings)  general.py (GeneralSettings)
    db/                 settings.py  lifehooks.py (engine)  healthcheck.py  models.py (Record, model discovery)
    cache/              settings.py  lifehooks.py (Cache)  healthcheck.py  base.py (keys, data version)
    healthcheck/        handler.py (/healthcheck, 503 on failure)  schemas.py
    errors.py           ServiceError hierarchy, mapped to status codes in one handler
    openapi.py          Pydantic models for documented responses and headers
    validators.py       shared Pydantic validators
  clients/              schemas.py  models.py  repository.py  router.py
  documents/            schemas.py  models.py  repository.py  router.py  chunking.py
  embeddings/           settings.py  service.py  lifehooks.py  constants.py
  search/               settings.py  schemas.py  retrievers.py  fusion.py  service.py  router.py
                        synonyms.py  synonyms.txt  lifehooks.py
  summary/              settings.py  schemas.py  service.py  depends.py  router.py  lifehooks.py
tests/                  mirrors the packages: core/ clients/ documents/ search/ summary/
migrations/             Alembic; env.py discovers every `*.models` module
```

## Module roles

Every package uses the same file names for the same job, so you always know where to look:

| File | Holds |
|---|---|
| `settings.py` | A Pydantic mixin with the package's settings, in SCREAMING_SNAKE_CASE because the field names double as environment variables. |
| `schemas.py` | Pydantic models for requests and responses. |
| `models.py` | Database tables. |
| `repository.py` | SQLAlchemy Core statements. |
| `service.py` | Business logic that composes repositories. |
| `router.py` | The FastAPI router. |
| `depends.py` | FastAPI dependencies. |
| `lifehooks.py` | Lifespans: startup and shutdown work. |
| `healthcheck.py` | Readiness probes. |

## Settings

`settings.py` composes one `Settings` class from the capability mixins, as FastLoom does:

```python
class Settings(
    GeneralSettings,  # PROJECT_NAME, PROJECT_VERSION, .env loading, empty values ignored
    LauncherSettings,  # APP_HOST, APP_PORT, WORKERS, RELOAD
    PostgresSettings,  # DATABASE_URL
    RedisSettings,  # REDIS_URL, REDIS_KEY_PREFIX
    EmbeddingSettings,  # EMBEDDING_MODEL, EMBEDDING_CACHE_DIR, CHUNK_MAX_WORDS, ...
    SearchSettings,  # thresholds, RRF_K, SYNONYMS_PATH, SEARCH_CACHE_TTL_SECONDS
    SummarySettings,  # ANTHROPIC_API_KEY, SUMMARY_MODEL, ...
): ...
```

`get_settings()` is an `lru_cache` getter. `core/` never imports the service's `Settings`: capability functions take what they need as arguments (`get_engine(url)`, `get_cache(url, prefix)`, `postgres_check(url)`), so the framework stays independent of the service built on it. Every variable is listed in [settings.md](settings.md).

## The App declaration and the launcher

`app.py` declares the service as data, and `core/launcher/main.py:create_app` turns that into a FastAPI instance:

```python
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
```

`create_app` does the following:

* Mounts every route under `api_prefix`. The feature routers don't know the version prefix.
* Builds the OpenAPI tag list from the routes' `Tag` models.
* Names operation ids after the route functions.
* Registers `/healthcheck` outside the version prefix.
* Maps every `ServiceError` to its status code.
* Combines the lifespans: they enter in order and exit in reverse.

`launch` (a `[project.scripts]` entrypoint) runs uvicorn on the `build_app` factory using `APP_HOST`, `APP_PORT`, `WORKERS` and `RELOAD`; the Docker image starts with it.

## Schemas and tables

Tables are Pydantic models too: [SQLModel](https://sqlmodel.tiangolo.com/), which maps a Pydantic model to a SQLAlchemy table. Each entity follows one hierarchy:

| Class | Where | Purpose |
|---|---|---|
| `ClientBase` | `clients/schemas.py` | Fields the API accepts. Validation (trimmed, bounded strings, emails, URLs, no NUL characters) and column types (`TEXT`, `TEXT[]`) are defined once, here. |
| `ClientIn` | `clients/schemas.py` | Request body (`ClientBase` plus the Swagger example). |
| `ClientOut` | `clients/schemas.py` | `ClientBase` plus `Record` (`id`, `created_at`). |
| `Client` | `clients/models.py` | The table: `ClientBase` plus `Record`, plus the generated search columns and indexes, which never leave the database. |

`Record` (in `core/db/models.py`) is shared by both sides of the hierarchy. On a table it becomes the UUID primary key with `gen_random_uuid()` and a `created_at` column defaulting to `now()`. On an `...Out` model it gives the same two read-only fields.

Repositories still write SQLAlchemy Core statements against these classes (`insert(Client).values(...)`, `select(col(Client.id))`); no ORM sessions or identity map. `sqlmodel.col()` gives the type checker a column expression instead of the field's Python type.

## Errors

`core/errors.py` defines `ServiceError` with a `status_code` class attribute: `NotFoundError` 404, `ConflictError` 409, `UpstreamError` 502, `UnavailableError` 503. A single exception handler serialises any of them as `{"detail": "..."}`.

Routers document their errors from the same classes, `responses=NotFoundError.documented("Unknown client")`, so the documented status code and the status code actually returned can't drift apart. Provider failures are translated where they occur: `ClaudeSummarizer` turns `anthropic.APIError` into `UpstreamError`, so the HTTP layer needs no provider-specific handler.

## Healthcheck

`/healthcheck` runs every registered check in order. Each check opens a fresh connection with a 2-second timeout instead of reusing the pool, so stale connections can't hide a dead dependency. The endpoint returns `{"status": "ok"}`, or 503 with the first failure, for example `{"detail": "ConnectionError: Error -2 connecting to redis:6379. ..."}`. Docker Compose uses it as the API container's health check.

## Data model and migrations

* `clients`: UUID primary key and a unique index on `lower(email)`, so `John.Doe@X.com` conflicts with `john.doe@x.com`. Social links are a `text[]`. Two generated columns, `search_text` (trigram GIN index) and `description_tsv` (GIN index), feed search.
* `documents`: foreign key to `clients` with `ON DELETE CASCADE`, and a generated weighted `search_tsv` column (GIN index).
* `document_chunks`: `(document_id, chunk_index)` primary key, passage text, and a `vector(384)` with an HNSW cosine index.

Invariants live in the database (unique email, foreign keys); the API maps the violations to 409 and 404. Migrations are Alembic, autogenerated from the SQLModel metadata. `migrations/env.py` calls `discover_metadata(nevis_search)`, which imports every `*.models` module the way FastLoom's `models_module` does, so a new table is picked up without editing `env.py`. The first revision enables `vector` and `pg_trgm`. Migrations run in a one-shot `migrate` container before the API starts, never inside the app.

## Adding a feature

1. Create `nevis_search/<feature>/` with the modules it needs from the table above.
2. If it has settings, add its mixin to `Settings` in `settings.py`.
3. Register its router as a `Route` in `app.py`. If it needs startup or shutdown work, add a lifespan; if it depends on a new external service, add a healthcheck.
4. Run `uv run alembic revision --autogenerate` if it adds tables.
5. Add tests under `tests/<feature>/`.
