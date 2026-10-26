from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from nevis_search.core.launcher.schemas import HealthCheck


def postgres_check(url: str) -> HealthCheck:
    async def check() -> None:
        engine = create_async_engine(url, poolclass=NullPool, connect_args={"connect_timeout": 2})
        try:
            async with engine.connect() as conn:
                await conn.execute(select(1))
        finally:
            await engine.dispose()

    return check
