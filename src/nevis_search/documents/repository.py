import asyncio
from collections.abc import Sequence
from uuid import UUID

from psycopg.errors import ForeignKeyViolation
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlmodel import col

from nevis_search.clients.repository import ensure_client
from nevis_search.core.cache.lifehooks import get_cache
from nevis_search.core.db.lifehooks import get_engine
from nevis_search.core.errors import NotFoundError
from nevis_search.documents.chunking import chunk_text
from nevis_search.documents.models import Document, DocumentChunk
from nevis_search.documents.schemas import DocumentIn, DocumentOut
from nevis_search.embeddings.service import load_embedder
from nevis_search.settings import get_settings

DOCUMENT_COLUMNS = (
    col(Document.id),
    col(Document.client_id),
    col(Document.title),
    col(Document.content),
    col(Document.created_at),
)


async def create_document(client_id: UUID, payload: DocumentIn) -> DocumentOut:
    settings = get_settings()
    engine = get_engine(settings.DATABASE_URL)
    async with engine.connect() as conn:
        await ensure_client(conn, client_id)
    chunks = chunk_text(payload.content, settings.CHUNK_MAX_WORDS)
    vectors = await asyncio.to_thread(
        load_embedder(settings).embed_passages, [f"{payload.title}\n{chunk}" for chunk in chunks]
    )
    try:
        async with engine.begin() as conn:
            row = (
                await conn.execute(
                    insert(Document).values(client_id=client_id, **payload.model_dump()).returning(*DOCUMENT_COLUMNS)
                )
            ).one()
            await conn.execute(
                insert(DocumentChunk),
                [
                    {"document_id": row.id, "chunk_index": index, "content": chunk, "embedding": vector}
                    for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
                ],
            )
    except IntegrityError as exc:
        if isinstance(exc.orig, ForeignKeyViolation):
            raise NotFoundError("client", client_id) from exc
        raise
    await get_cache(settings.REDIS_URL, settings.REDIS_KEY_PREFIX).bump_data_version()
    return DocumentOut.model_validate(row, from_attributes=True)


async def get_document(document_id: UUID) -> DocumentOut:
    async with get_engine(get_settings().DATABASE_URL).connect() as conn:
        row = (await conn.execute(select(*DOCUMENT_COLUMNS).where(col(Document.id) == document_id))).one_or_none()
    if row is None:
        raise NotFoundError("document", document_id)
    return DocumentOut.model_validate(row, from_attributes=True)


async def get_documents(document_ids: Sequence[UUID]) -> dict[UUID, DocumentOut]:
    async with get_engine(get_settings().DATABASE_URL).connect() as conn:
        rows = (await conn.execute(select(*DOCUMENT_COLUMNS).where(col(Document.id).in_(document_ids)))).all()
    return {row.id: DocumentOut.model_validate(row, from_attributes=True) for row in rows}


async def list_client_documents(client_id: UUID) -> list[DocumentOut]:
    async with get_engine(get_settings().DATABASE_URL).connect() as conn:
        await ensure_client(conn, client_id)
        rows = (
            await conn.execute(
                select(*DOCUMENT_COLUMNS)
                .where(col(Document.client_id) == client_id)
                .order_by(col(Document.created_at).desc())
            )
        ).all()
    return [DocumentOut.model_validate(row, from_attributes=True) for row in rows]
