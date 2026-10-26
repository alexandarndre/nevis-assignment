# Cache

Code: `src/nevis_search/core/cache/`. `Cache` wraps one Redis client. It builds namespaced keys (`<REDIS_KEY_PREFIX>:<namespace>:<sha256 of the parts>`) and owns a global data-version counter. Feature code reaches it through `get_cache(url, prefix)`, an `lru_cache` getter, and the cache lifespan closes the client on shutdown.

| Key | Value | Invalidation |
|---|---|---|
| `nevis:embedding:<sha256(model, q)>` | query vector (float32 bytes) | none needed, TTL 7 days |
| `nevis:search:<sha256(data version, params)>` | serialized search response | data version bumped after every committed write; TTL 5 min |
| `nevis:summary:<sha256(model, title, content)>` | summary JSON | content-addressed, TTL 30 days |
| `nevis:data-version` | integer | incremented by every client or document write; no TTL |

* **Freshness:** every client or document write increments the data version after its transaction commits, and the search key includes the version. A cached response can therefore never outlive the data it was built from, and no key scanning is needed.
* **Eviction:** Redis runs with `volatile-lru`, so only keys with a TTL can be evicted and the data version (no TTL) survives memory pressure.
* **Embeddings:** query embeddings stay valid across writes, so even after an invalidation a repeated query skips the model.
* **Summaries:** keyed by content hash and model, so an LLM call is paid once per document version.
* **Visibility:** the `X-Cache: HIT|MISS` response header on `/api/v1/search` shows whether Redis served the response.

Redis errors are not swallowed. A Redis outage fails the request and turns `/healthcheck` to 503.
