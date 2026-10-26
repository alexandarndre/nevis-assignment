import html
from functools import reduce
from typing import Any
from uuid import UUID

from sqlalchemy import Float, Integer, Text, and_, func, literal, or_, select
from sqlalchemy.dialects.postgresql import ARRAY, distinct_on
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import col

from nevis_search.clients.models import Client
from nevis_search.documents.models import Document, DocumentChunk
from nevis_search.embeddings.service import Vector
from nevis_search.search.fusion import client_fields
from nevis_search.search.schemas import HitType, Match, MatchSource, SearchParams
from nevis_search.search.settings import SearchSettings
from nevis_search.search.synonyms import SynonymGroup

# NOTE: SQLAlchemy's tsquery functions are GenericFunction[Any]; there is no typed tsquery expression.
type TsQuery = ColumnElement[Any]

TS_CONFIG = "english"
_MARK_START, _MARK_STOP = "⟦", "⟧"
_HEADLINE_OPTIONS = f"MaxFragments=2, MinWords=8, MaxWords=24, StartSel={_MARK_START}, StopSel={_MARK_STOP}"
_SNIPPET_CHARS = 300


def either(left: TsQuery, right: TsQuery) -> TsQuery:
    return left.op("||")(right)


def truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


def highlight(headline: str) -> str:
    return html.escape(headline, quote=False).replace(_MARK_START, "<mark>").replace(_MARK_STOP, "</mark>")


async def fuzzy_clients(conn: AsyncConnection, params: SearchParams, settings: SearchSettings) -> list[Match]:
    stmt = (
        select(
            col(Client.id),
            func.word_similarity(params.q, col(Client.first_name) + " " + col(Client.last_name)).label("name_sim"),
            func.word_similarity(params.q, col(Client.email)).label("email_sim"),
        )
        .where(literal(params.q).bool_op("<%")(col(Client.search_text)))
        .order_by(func.word_similarity(params.q, col(Client.search_text)).desc(), col(Client.id))
        .limit(settings.RETRIEVER_DEPTH)
    )
    if params.client_id is not None:
        stmt = stmt.where(col(Client.id) == params.client_id)
    return [
        Match(
            kind=HitType.CLIENT,
            id=row.id,
            sources=client_fields(row.name_sim, row.email_sim, settings.CLIENT_MATCH_THRESHOLD),
        )
        for row in await conn.execute(stmt)
    ]


async def described_clients(
    conn: AsyncConnection, params: SearchParams, settings: SearchSettings, tsquery: TsQuery
) -> list[Match]:
    stmt = (
        select(col(Client.id))
        .where(col(Client.description_tsv).bool_op("@@")(tsquery))
        .order_by(func.ts_rank_cd(col(Client.description_tsv), tsquery).desc(), col(Client.id))
        .limit(settings.RETRIEVER_DEPTH)
    )
    if params.client_id is not None:
        stmt = stmt.where(col(Client.id) == params.client_id)
    return [
        Match(kind=HitType.CLIENT, id=row.id, sources=frozenset({MatchSource.DESCRIPTION}))
        for row in await conn.execute(stmt)
    ]


async def synonym_query(conn: AsyncConnection, q: str, groups: tuple[SynonymGroup, ...]) -> TsQuery | None:
    synonyms = (
        func.unnest(
            literal([index for index, group in enumerate(groups) for _ in group.terms], ARRAY(Integer)),
            literal([term for group in groups for term in group.terms], ARRAY(Text)),
        )
        .table_valued("group_id", "term")
        .render_derived()
    )
    query = func.plainto_tsquery(TS_CONFIG, q)
    term = func.plainto_tsquery(TS_CONFIG, synonyms.c.term)
    triggered = set(
        (
            await conn.execute(
                select(synonyms.c.group_id)
                .distinct()
                .where(
                    or_(
                        func.to_tsvector(TS_CONFIG, q).bool_op("@@")(term),
                        and_(func.numnode(query) > 0, term.bool_op("@>")(query)),
                    )
                )
            )
        ).scalars()
    )
    terms = [term for index, group in enumerate(groups) if index in triggered for term in group.terms]
    if len(terms) == 0:
        return None
    phrases: list[TsQuery] = [func.phraseto_tsquery(TS_CONFIG, term) for term in terms]
    return reduce(either, phrases)


async def lexical_documents(
    conn: AsyncConnection, params: SearchParams, settings: SearchSettings, tsquery: TsQuery, source: MatchSource
) -> list[Match]:
    stmt = (
        select(col(Document.id))
        .where(col(Document.search_tsv).bool_op("@@")(tsquery))
        .order_by(func.ts_rank_cd(col(Document.search_tsv), tsquery).desc(), col(Document.id))
        .limit(settings.RETRIEVER_DEPTH)
    )
    if params.client_id is not None:
        stmt = stmt.where(col(Document.client_id) == params.client_id)
    return [Match(kind=HitType.DOCUMENT, id=row.id, sources=frozenset({source})) for row in await conn.execute(stmt)]


async def semantic_documents(
    conn: AsyncConnection, params: SearchParams, settings: SearchSettings, vector: Vector
) -> list[Match]:
    distance = col(DocumentChunk.embedding).op("<=>", return_type=Float)(vector)
    nearest = (
        select(col(DocumentChunk.document_id), col(DocumentChunk.content), (1 - distance).label("similarity"))
        .order_by(distance)
        .limit(settings.RETRIEVER_DEPTH * 4)
    )
    if params.client_id is not None:
        nearest = nearest.join(Document, col(Document.id) == col(DocumentChunk.document_id)).where(
            col(Document.client_id) == params.client_id
        )
    chunks = nearest.subquery()
    best = (
        select(chunks.c.document_id, chunks.c.content, chunks.c.similarity)
        .where(chunks.c.similarity >= settings.SEMANTIC_MIN_SIMILARITY)
        .ext(distinct_on(chunks.c.document_id))
        .order_by(chunks.c.document_id, chunks.c.similarity.desc())
        .subquery()
    )
    stmt = select(best).order_by(best.c.similarity.desc(), best.c.document_id).limit(settings.RETRIEVER_DEPTH)
    return [
        Match(
            kind=HitType.DOCUMENT,
            id=row.document_id,
            sources=frozenset({MatchSource.SEMANTIC}),
            snippet=html.escape(truncate(row.content, _SNIPPET_CHARS), quote=False),
        )
        for row in await conn.execute(stmt)
    ]


async def headlines(conn: AsyncConnection, document_ids: list[UUID], tsquery: TsQuery) -> dict[UUID, str]:
    if len(document_ids) == 0:
        return {}
    rows = await conn.execute(
        select(
            col(Document.id),
            func.ts_headline(
                TS_CONFIG,
                func.translate(col(Document.content), _MARK_START + _MARK_STOP, ""),
                tsquery,
                _HEADLINE_OPTIONS,
            ).label("headline"),
        ).where(col(Document.id).in_(document_ids))
    )
    return {row.id: highlight(row.headline) for row in rows}
