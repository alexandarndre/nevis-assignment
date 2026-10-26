from collections.abc import Sequence
from uuid import UUID

from psycopg.errors import UniqueViolation
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlmodel import col

from nevis_search.clients.models import Client
from nevis_search.clients.schemas import ClientIn, ClientOut
from nevis_search.core.cache.lifehooks import get_cache
from nevis_search.core.db.lifehooks import get_engine
from nevis_search.core.errors import ConflictError, NotFoundError
from nevis_search.settings import get_settings

CLIENT_COLUMNS = (
    col(Client.id),
    col(Client.first_name),
    col(Client.last_name),
    col(Client.email),
    col(Client.description),
    col(Client.social_links),
    col(Client.created_at),
)


async def create_client(payload: ClientIn) -> ClientOut:
    settings = get_settings()
    try:
        async with get_engine(settings.DATABASE_URL).begin() as conn:
            row = (
                await conn.execute(insert(Client).values(**payload.model_dump(mode="json")).returning(*CLIENT_COLUMNS))
            ).one()
    except IntegrityError as exc:
        if isinstance(exc.orig, UniqueViolation):
            raise ConflictError(f"a client with email {payload.email} already exists") from exc
        raise
    await get_cache(settings.REDIS_URL, settings.REDIS_KEY_PREFIX).bump_data_version()
    return ClientOut.model_validate(row, from_attributes=True)


async def ensure_client(conn: AsyncConnection, client_id: UUID) -> None:
    if (await conn.execute(select(col(Client.id)).where(col(Client.id) == client_id))).one_or_none() is None:
        raise NotFoundError("client", client_id)


async def get_client(client_id: UUID) -> ClientOut:
    async with get_engine(get_settings().DATABASE_URL).connect() as conn:
        row = (await conn.execute(select(*CLIENT_COLUMNS).where(col(Client.id) == client_id))).one_or_none()
    if row is None:
        raise NotFoundError("client", client_id)
    return ClientOut.model_validate(row, from_attributes=True)


async def get_clients(client_ids: Sequence[UUID]) -> dict[UUID, ClientOut]:
    async with get_engine(get_settings().DATABASE_URL).connect() as conn:
        rows = (await conn.execute(select(*CLIENT_COLUMNS).where(col(Client.id).in_(client_ids)))).all()
    return {row.id: ClientOut.model_validate(row, from_attributes=True) for row in rows}
