# Settings

`Settings` (in `src/nevis_search/settings.py`) is composed from one Pydantic mixin per capability. Field names are the environment variable names. Values come from the environment or from a `.env` file, and an empty value counts as unset (`ANTHROPIC_API_KEY=` disables the LLM).

| Variable | Default | Mixin | Purpose |
|---|---|---|---|
| `PROJECT_NAME` | `Nevis Search API` | `ProjectSettings` | OpenAPI title |
| `PROJECT_VERSION` | `1.0.0` | `ProjectSettings` | OpenAPI document version |
| `APP_HOST` | `0.0.0.0` | `LauncherSettings` | bind address for `launch` |
| `APP_PORT` | `8000` | `LauncherSettings` | bind port for `launch` |
| `WORKERS` | `1` | `LauncherSettings` | uvicorn workers; each loads its own copy of the embedding model (about 270 MB) |
| `RELOAD` | `false` | `LauncherSettings` | uvicorn auto-reload for local development |
| `DATABASE_URL` | `postgresql+psycopg://nevis:nevis@localhost:55432/nevis` | `PostgresSettings` | Postgres (psycopg 3 driver) |
| `REDIS_URL` | `redis://localhost:56379/0` | `RedisSettings` | Redis |
| `REDIS_KEY_PREFIX` | `nevis` | `RedisSettings` | namespace for every cache key |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | `EmbeddingSettings` | must produce 384-d vectors (checked at startup) |
| `EMBEDDING_CACHE_DIR` | fastembed default | `EmbeddingSettings` | model files; `/app/models` in the image |
| `EMBEDDING_CACHE_TTL_SECONDS` | `604800` | `EmbeddingSettings` | cached query vectors |
| `CHUNK_MAX_WORDS` | `120` | `EmbeddingSettings` | passage size |
| `CLIENT_MATCH_THRESHOLD` | `0.5` | `SearchSettings` | trigram word similarity cutoff |
| `SEMANTIC_MIN_SIMILARITY` | `0.6` | `SearchSettings` | cosine similarity cutoff for passages |
| `RETRIEVER_DEPTH` | `50` | `SearchSettings` | candidates per retriever before fusion |
| `RRF_K` | `60` | `SearchSettings` | RRF damping constant |
| `SYNONYMS_PATH` | packaged `synonyms.txt` | `SearchSettings` | synonym groups file |
| `SEARCH_CACHE_TTL_SECONDS` | `300` | `SearchSettings` | cached search responses |
| `ANTHROPIC_API_KEY` | unset | `SummarySettings` | enables LLM summaries |
| `SUMMARY_MODEL` | `claude-haiku-5-5` | `SummarySettings` | Claude model for summaries |
| `SUMMARY_SENTENCES` | `3` | `SummarySettings` | length of extractive summaries |
| `SUMMARY_CACHE_TTL_SECONDS` | `2592000` | `SummarySettings` | cached summaries |

The local defaults match the ports `docker-compose.yml` publishes for Postgres and Redis. `.env.example` lists the variables you are most likely to change.
