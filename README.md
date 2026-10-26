# Nevis Search API

A search API for wealth advisors across clients and their documents. One query box finds clients by name, email or description (typo tolerant) and documents by keywords, by domain synonyms and by meaning. A document summary is available on demand.

* `GET /api/v1/search?q=NevisWealth` returns the clients whose email is `@neviswealth.com`.
* `GET /api/v1/search?q=address proof` returns the utility bill, the tenancy agreement and the bank statement, none of which contain the words "address proof".

Stack: Python 3.13, FastAPI, PostgreSQL 17 with `pgvector` and `pg_trgm`, Redis, SQLModel (Pydantic models mapped to SQLAlchemy tables) + Alembic, `fastembed` (local ONNX embeddings), optional Claude for summaries, managed with `uv`, shipped with Docker Compose. The code is laid out like [FastLoom](https://github.com/aradng/FastLoom): a small capability-based framework in `core/`, one package per feature, and a declarative `App` in `app.py` (see [docs/architecture.md](docs/architecture.md)).

## Quick start

Requirements: Docker with Compose v2.

```bash
docker compose up --build -d                              # db, redis, migrations, api on :8000, then demo data
curl -s 'localhost:8000/api/v1/search?q=address%20proof' | jq
```

* Swagger UI: http://localhost:8000/docs ("Try it out" is on by default; the search query field offers example queries)
* ReDoc: http://localhost:8000/redoc
* OpenAPI 3.1 document: [`docs/openapi.json`](docs/openapi.json) (also served at `/openapi.json`)

LLM summaries are optional. Without a key, summaries are extractive and everything works offline. To use Claude:

```bash
ANTHROPIC_API_KEY=sk-ant-... docker compose up -d
```

The one-shot `seed` service loads 6 demo clients and 13 documents once the API is healthy (about 20 seconds after `up`). It is idempotent: clients that already exist are skipped, so restarts never duplicate data. `docker compose down -v` wipes the database, and the next `up` seeds it again.

## Local development

```bash
uv sync                                       # Python 3.13 venv with dev tools
docker compose up -d db redis                 # Postgres on 127.0.0.1:55432, Redis on 127.0.0.1:56379
uv run alembic upgrade head
RELOAD=true uv run launch                     # API on :8000 with auto-reload
uv run seed
```

The settings defaults point at those ports; override any of them with an environment variable or a `.env` file. Every variable is listed in [docs/settings.md](docs/settings.md).

### Tests and checks

```bash
uv run pytest          # 92 tests; starts throwaway Postgres (pgvector) and Redis containers via testcontainers
uv run mypy            # strict mode, src + tests + migrations
uv run ruff check && uv run ruff format --check
```

The integration tests need a Docker daemon. With Colima, export the socket first:

```bash
export DOCKER_HOST=unix://$HOME/.colima/default/docker.sock TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock
```

Tests mirror the packages (`tests/core`, `tests/clients`, `tests/documents`, `tests/search`, `tests/summary`). What is covered: the launcher (healthcheck 200/503, lifespan ordering, error-to-status mapping), settings composition, chunking, rank fusion, synonym parsing (including a check that no multi-word synonym collapses to a single word after stopword removal), validation edge cases (blank/oversized input, NUL characters, bad UUIDs, bad emails and URLs), HTTP status codes (201 + `Location`, 404, 409, 422, 502, 503), case-insensitive email uniqueness, the two examples from the brief, typo tolerance, semantic recall without shared keywords, filters, HTML escaping of snippets, cache hits and cache invalidation on writes, the Claude request contract and provider failures (against a mocked transport), refusal fallback, summary caching, and the API surface itself (versioned paths, operation ids, described tags, the documented `X-Cache` header, and that the Swagger response example validates against the schema).

## API

| Method | Operation id | Path | Purpose | Codes |
|---|---|---|---|---|
| `POST` | `create_client` | `/api/v1/clients` | Create a client | 201, 409 email taken, 422 |
| `GET` | `get_client` | `/api/v1/clients/{id}` | Get a client | 200, 404, 422 |
| `POST` | `create_document` | `/api/v1/clients/{id}/documents` | Upload a document (indexed synchronously) | 201, 404 unknown client, 422 |
| `GET` | `list_documents` | `/api/v1/clients/{id}/documents` | List a client's documents, newest first | 200, 404 |
| `GET` | `get_document` | `/api/v1/documents/{id}` | Get a document | 200, 404 |
| `GET` | `get_document_summary` | `/api/v1/documents/{id}/summary` | Summarize a document | 200, 404, 502 LLM failure |
| `GET` | `search` | `/api/v1/search` | Search clients and documents | 200, 422 |
| `GET` | `healthcheck` | `/healthcheck` | Database and Redis readiness | 200, 503 names the failing dependency |

`POST` responses carry a `Location` header with the versioned path of the new resource. Errors use `{"detail": "..."}`; validation errors use FastAPI's standard 422 body.

### Versioning

The brief's endpoints (`/clients`, `/clients/{id}/documents`, `/search`) are served under the `/api/v1` prefix.

* A breaking change (removing or renaming a field, changing a type or a status code, changing search semantics a client relies on) ships as `/api/v2`, mounted next to `/api/v1` in the same app. Both are served until clients have moved, and the OpenAPI document lists both.
* Additive changes (new endpoints, new optional parameters, new response fields) stay in v1, so clients must ignore unknown fields.
* `/healthcheck`, `/docs`, `/redoc` and `/openapi.json` describe or probe the service rather than being part of the contract, so they are unversioned. The compose health check therefore never changes with the API version.
* Operation ids are the route names (`create_client`, `search`, ...) rather than FastAPI's generated `create_client_clients_post`, so a generated SDK has readable method names. A v2 router would prefix its route names (`v2_search`) to keep ids unique.
* The prefix is declared once, `App(api_prefix="/api/v1", routes=[...])` in `app.py`, and the launcher mounts every route under it. The feature routers know nothing about the version, and `Location` headers are built with `url_path_for`.

### Search parameters

`GET /api/v1/search`:

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `q` | string, 1-256 chars | required | whitespace is trimmed and collapsed |
| `type` | `client` \| `document` | both | restrict the kind of hit |
| `client_id` | UUID | none | restrict to one client and their documents |
| `limit` | 1-50 | 10 | |

The response is a JSON array ordered by `score`. Every hit has `type`, `score` and `matched_by` (which retrievers found it: `name`, `email`, `description`, `keyword`, `synonym`, `semantic`). Client hits embed the `Client` schema; document hits embed the `Document` schema plus a `snippet`. The `X-Cache: HIT|MISS` header shows whether Redis served the response.

The data model follows the brief. The extensions: `Client.created_at`, and on search hits `score`, `matched_by` and `snippet`.

## Example queries and responses

Captured from the Compose stack after running the seed script. Ids are shortened and long fields elided with `...`; everything else is verbatim. Hits with tied scores are ordered by id, so their order can differ between runs.

**Company name finds clients by email domain**

```http
GET /api/v1/search?q=NevisWealth
```

```json
[
  {
    "score": 0.016393,
    "matched_by": ["email"],
    "type": "client",
    "client": {
      "first_name": "John",
      "last_name": "Doe",
      "email": "john.doe@neviswealth.com",
      "description": "Founder of a fintech start-up. Prefers growth portfolios with an ESG tilt.",
      "social_links": ["https://www.linkedin.com/in/johndoe"],
      "id": "86e608d1-...",
      "created_at": "2026-10-25T15:19:50.620272Z"
    }
  },
  {
    "score": 0.016129,
    "matched_by": ["email"],
    "type": "client",
    "client": { "first_name": "Sophie", "last_name": "Martin", "email": "sophie.martin@neviswealth.com", "...": "..." }
  }
]
```

**"address proof" finds proof-of-address documents that never use those words**

```http
GET /api/v1/search?q=address proof&type=document
```

```json
[
  {
    "score": 0.016393,
    "matched_by": ["synonym"],
    "type": "document",
    "snippet": "British <mark>Gas</mark> <mark>electricity</mark> and <mark>gas</mark> <mark>statement</mark> for",
    "document": {
      "title": "Utility bill - British Gas, March 2024",
      "content": "British Gas electricity and gas statement for the billing period 1 to 31 March 2024. Account holder: John Doe, 12 Baker Street, London NW1 6XE. ...",
      "id": "...", "client_id": "...", "created_at": "..."
    }
  },
  { "score": 0.016129, "matched_by": ["synonym"], "type": "document", "snippet": "Assured shorthold <mark>tenancy</mark> for Flat 4, 22 Kensington", "document": { "title": "Tenancy agreement", "...": "..." } },
  { "score": 0.015873, "matched_by": ["synonym"], "type": "document", "snippet": "Current account <mark>statement</mark> <mark>addressed</mark>", "document": { "title": "Bank statement - Millennium BCP, June 2024", "...": "..." } }
]
```

**Meaning without shared keywords (semantic retriever)**

```http
GET /api/v1/search?q=selling the company
```

```json
[
  {
    "score": 0.016393,
    "matched_by": ["semantic"],
    "type": "document",
    "snippet": "Draft agreement for the sale of O'Connor Logistics Ltd to Freightline Group for 12.5m EUR, with an earn-out of up to 2m EUR over two years. Completion is targeted for Q2 2027.",
    "document": { "title": "Share purchase agreement (draft)", "...": "..." }
  },
  { "score": 0.016129, "matched_by": ["semantic"], "type": "document", "snippet": "The client's wealth derives from an inheritance received in 2018 ...", "document": { "title": "Source of wealth declaration", "...": "..." } }
]
```

**Agreement between retrievers ranks first**

```http
GET /api/v1/search?q=gilts
```

```json
[
  {
    "score": 0.032787,
    "matched_by": ["keyword", "semantic"],
    "type": "document",
    "snippet": "SIPP and moving 40% of the portfolio into short-dated <mark>gilts</mark>. The client wants to fund private school fees for her grandchildren from",
    "document": { "title": "Review meeting notes, 14 May 2024", "...": "..." }
  }
]
```

**Typos and descriptions**

```http
GET /api/v1/search?q=Jonh Doe        ->  John Doe, matched_by ["name", "email"]
GET /api/v1/search?q=surgeon         ->  Maria Garcia, matched_by ["description"]
GET /api/v1/search?q=chocolate cake  ->  []
```

**Create a client and a document**

```http
POST /api/v1/clients
{"first_name": "Emma", "last_name": "Stone", "email": "emma.stone@neviswealth.com",
 "description": "Architect saving for early retirement.", "social_links": ["https://www.linkedin.com/in/emmastone"]}

HTTP/1.1 201 Created
location: /api/v1/clients/2f4374f4-...
{"first_name": "Emma", "last_name": "Stone", "email": "emma.stone@neviswealth.com", "description": "Architect saving for early retirement.",
 "social_links": ["https://www.linkedin.com/in/emmastone"], "id": "2f4374f4-...", "created_at": "2026-10-25T15:19:51.136924Z"}
```

```http
POST /api/v1/clients/2f4374f4-.../documents
{"title": "Council tax bill 2024/25", "content": "Westminster City Council tax bill for 5 Abbey Road, London NW8, band E, annual charge 1,890 GBP."}

HTTP/1.1 201 Created
location: /api/v1/documents/80295d92-...
{"title": "Council tax bill 2024/25", "content": "...", "id": "80295d92-...", "client_id": "2f4374f4-...", "created_at": "2026-10-25T15:19:51.191776Z"}
```

**Errors**

```http
POST /api/v1/clients  {"first_name": "Emma", "last_name": "Stone", "email": "Emma.Stone@NevisWealth.com"}
409 {"detail": "a client with email Emma.Stone@neviswealth.com already exists"}

POST /api/v1/clients/00000000-0000-0000-0000-000000000000/documents
404 {"detail": "client 00000000-0000-0000-0000-000000000000 not found"}

GET /api/v1/search?q=%20
422 {"detail": [{"type": "string_too_short", "loc": ["query", "q"], "msg": "String should have at least 1 character", ...}]}
```

**Summary**

```http
GET /api/v1/documents/{id}/summary
```

```json
{
  "summary": "Discussed drawing down from the SIPP and moving 40% of the portfolio into short-dated gilts. The client wants to fund private school fees for her grandchildren from 2025. Next review in November.",
  "method": "extractive",
  "model": "BAAI/bge-small-en-v1.5",
  "document_id": "00c48713-..."
}
```

With `ANTHROPIC_API_KEY` set, `method` is `llm` and `model` is `claude-haiku-5-5`.

## How it works

Short version below; the details are in `docs/`:

* [docs/architecture.md](docs/architecture.md): layout, settings composition, the `App` declaration and launcher, schemas and SQLModel tables, errors, healthcheck, data model and migrations, how to add a feature.
* [docs/search.md](docs/search.md): the five retrievers, Reciprocal Rank Fusion, why there is a synonym retriever (with the embedding-model measurements), passage chunking, the similarity cutoff, safe snippets.
* [docs/cache.md](docs/cache.md): Redis keys, invalidation by data version, eviction policy.
* [docs/settings.md](docs/settings.md): every environment variable, grouped by settings mixin.

Search runs five retrievers in one Postgres transaction and merges them with Reciprocal Rank Fusion:

* trigram similarity on name and email;
* full text on the client description;
* full text on documents;
* full text on synonym-expanded queries;
* `pgvector` similarity over document passages.

Redis caches query embeddings, search responses (invalidated by a data version bumped on every write) and summaries.

Summaries use Claude (`claude-haiku-5-5`, effort `low`) when `ANTHROPIC_API_KEY` is set. Without a key, or if the model declines, they fall back to the sentences closest to the document's embedding centroid. Provider failures, and answers cut off before the end, return 502.

## Design decisions and trade-offs

* **Postgres as the search engine instead of Elasticsearch/OpenSearch.** Full-text, trigram and vector search in the same transactional store means a document and its index entries are written in one transaction. There is no dual write, no sync lag and no second cluster to run. Elasticsearch would bring richer relevance tuning and analyzers at the cost of about 1.5 GB of RAM and a consistency problem between two stores. At advisor-book scale (thousands of clients, tens of thousands of documents) Postgres is comfortably fast; the retrievers are isolated functions, so moving to a dedicated engine later is contained.
* **Local embeddings instead of an embedding API.** Reproducible with no keys, no per-call cost, no client data leaving the deployment, which matters for wealth-management data. The measured trade-off is weaker domain knowledge, closed by the synonym file.
* **Hybrid retrieval with RRF instead of one clever score.** Each retriever stays simple and testable, and `matched_by` explains every hit.
* **Synchronous indexing.** Embedding a document happens in the upload request (off the event loop). Simple and immediately searchable; a large upload volume would move this to a queue and a worker.
* **Errors surface.** A Redis or database outage fails the request (and turns `/healthcheck` to 503) instead of silently serving partial results.
* **A small in-house framework instead of FastLoom itself.** The FastLoom layout (capability packages with `settings`/`lifehooks`/`healthcheck`, a declarative `App`, Settings mixins) keeps every concern in a predictable place. The framework needed here is about 300 lines, with no tenant, auth, broker or Mongo machinery to carry.
* **SQLModel for tables.** One Pydantic class hierarchy defines validation, column types and the read models together, so the API schema and the table cannot drift. Repositories still issue SQLAlchemy Core statements; no ORM session state.

## Limitations and next steps

* Trigram matching tolerates insertions and swaps of one or two letters (`Jonh`, `neviswelth`) but not every misspelling (`jhon`); `fuzzystrmatch` (Double Metaphone) on names would cover phonetic misspellings.
* Client descriptions are matched lexically only; embedding them would let "retired doctor" find "retired surgeon".
* The synonym file is hand-curated; at scale it would be maintained by compliance/ops or generated with an LLM per document at ingest (document expansion).
* No authentication or per-advisor data scoping, no update/delete endpoints and no pagination cursor, all outside the brief.
* The cache data version is bumped after the write commits. If Redis fails at exactly that moment the request returns 500 although the row is stored, and cached searches can be up to 5 minutes stale.
* Document upload embeds synchronously and accepts up to 200,000 characters (about 280 passages); there is no request-body size limit in front of the API. The client id is checked before any embedding work.
* With a `client_id` filter on a very large corpus, the approximate HNSW scan can return fewer passages than exist for that client; an exact scan for scoped queries would fix this at scale.
* Not deployed anywhere; the Compose stack is the reproducible artifact.

## Project layout

```
src/nevis_search/
  settings.py      Settings composed from the capability mixins
  app.py           App declaration (routes, healthchecks, lifespans) and the `launch` entrypoint
  seed.py          demo data loader (`seed` entrypoint)
  core/            framework: launcher/ settings/ db/ cache/ healthcheck/ errors.py openapi.py validators.py
  clients/         schemas.py models.py repository.py router.py
  documents/       schemas.py models.py repository.py router.py chunking.py
  embeddings/      settings.py service.py lifehooks.py constants.py
  search/          settings.py schemas.py retrievers.py fusion.py service.py router.py synonyms.py synonyms.txt lifehooks.py
  summary/         settings.py schemas.py service.py depends.py router.py lifehooks.py
migrations/        Alembic revisions (env.py discovers every *.models module)
tests/             mirrors the packages: core/ clients/ documents/ search/ summary/
docs/              architecture.md search.md cache.md settings.md openapi.json
```
