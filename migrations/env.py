from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

import nevis_search
from nevis_search.core.db.models import discover_metadata
from nevis_search.settings import get_settings

if context.config.config_file_name is not None:
    fileConfig(context.config.config_file_name)

engine = create_engine(get_settings().DATABASE_URL, poolclass=pool.NullPool)
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=discover_metadata(nevis_search), compare_type=True)
    with context.begin_transaction():
        context.run_migrations()
