import asyncio

import numpy as np
from sqlalchemy import func, select

from nevis_search.clients.repository import get_clients
from nevis_search.core.cache.base import Cache
from nevis_search.core.cache.lifehooks import get_cache
from nevis_search.core.db.lifehooks import get_engine
from nevis_search.documents.repository import get_documents
from nevis_search.embeddings.service import Vector, load_embedder
from nevis_search.search import retrievers
from nevis_search.search.fusion import fuse
from nevis_search.search.schemas import (
    SEARCH_HITS,
    ClientHit,
    DocumentHit,
    HitType,
    Match,
    MatchSource,
    SearchHit,
    SearchParams,
    SearchResponse,
)
from nevis_search.search.synonyms import load_synonyms
from nevis_search.settings import Settings, get_settings

_LEXICAL = frozenset({MatchSource.KEYWORD, MatchSource.SYNONYM})


async def search(params: SearchParams) -> SearchResponse:
    settings = get_settings()
    cache = get_cache(settings.REDIS_URL, settings.REDIS_KEY_PREFIX)
    key = cache.key("search", str(await cache.data_version()), params.model_dump_json())
    cached = await cache.get(key)
    if cached is not None:
        return SearchResponse(payload=cached, cache_hit=True)
    payload = SEARCH_HITS.dump_json(await run_search(params, settings, cache))
    await cache.set(key, payload, settings.SEARCH_CACHE_TTL_SECONDS)
    return SearchResponse(payload=payload, cache_hit=False)


async def run_search(params: SearchParams, settings: Settings, cache: Cache) -> list[SearchHit]:
    query_vector = None if params.type is HitType.CLIENT else await _query_vector(params.q, settings, cache)
    keyword_query: retrievers.TsQuery = func.plainto_tsquery(retrievers.TS_CONFIG, params.q)
    async with get_engine(settings.DATABASE_URL).begin() as conn:
        await conn.execute(
            select(
                func.set_config("pg_trgm.word_similarity_threshold", str(settings.CLIENT_MATCH_THRESHOLD), True),
                func.set_config("hnsw.ef_search", str(min(1000, max(40, settings.RETRIEVER_DEPTH * 4))), True),
                func.set_config("hnsw.iterative_scan", "relaxed_order", True),
            )
        )
        rankings: list[list[Match]] = []
        if params.type is not HitType.DOCUMENT:
            rankings += [
                await retrievers.fuzzy_clients(conn, params, settings),
                await retrievers.described_clients(conn, params, settings, keyword_query),
            ]
        highlight_query = keyword_query
        if query_vector is not None:
            rankings += [
                await retrievers.lexical_documents(conn, params, settings, keyword_query, MatchSource.KEYWORD),
                await retrievers.semantic_documents(conn, params, settings, query_vector),
            ]
            synonym_query = await retrievers.synonym_query(conn, params.q, load_synonyms(settings.SYNONYMS_PATH))
            if synonym_query is not None:
                rankings.append(
                    await retrievers.lexical_documents(conn, params, settings, synonym_query, MatchSource.SYNONYM)
                )
                highlight_query = retrievers.either(keyword_query, synonym_query)

        fused = fuse(rankings, settings.RRF_K, params.limit)
        document_ids = [hit_id for kind, hit_id in fused.ranked if kind is HitType.DOCUMENT]
        lexical_ids = [i for i in document_ids if not _LEXICAL.isdisjoint(fused.sources[(HitType.DOCUMENT, i)])]
        snippets = fused.snippets | await retrievers.headlines(conn, lexical_ids, highlight_query)

    clients = await get_clients([hit_id for kind, hit_id in fused.ranked if kind is HitType.CLIENT])
    documents = await get_documents(document_ids)
    return [
        ClientHit(score=round(fused.scores[key], 6), matched_by=fused.sources[key], client=clients[key[1]])
        if key[0] is HitType.CLIENT
        else DocumentHit(
            score=round(fused.scores[key], 6),
            matched_by=fused.sources[key],
            snippet=snippets[key[1]],
            document=documents[key[1]],
        )
        for key in fused.ranked
    ]


async def _query_vector(text: str, settings: Settings, cache: Cache) -> Vector:
    embedder = load_embedder(settings)
    key = cache.key("embedding", embedder.model_name, text)
    cached = await cache.get(key)
    if cached is not None:
        return np.frombuffer(cached, dtype=np.float32)
    vector = await asyncio.to_thread(embedder.embed_query, text)
    await cache.set(key, vector.tobytes(), settings.EMBEDDING_CACHE_TTL_SECONDS)
    return vector
