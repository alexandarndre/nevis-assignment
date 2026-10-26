import importlib
import pkgutil
from types import ModuleType
from uuid import UUID

from pydantic import AwareDatetime
from sqlalchemy import DateTime, MetaData, func, text
from sqlmodel import Field, SQLModel


class Record(SQLModel):
    id: UUID = Field(primary_key=True, sa_column_kwargs={"server_default": text("gen_random_uuid()")})
    created_at: AwareDatetime = Field(sa_type=DateTime(timezone=True), sa_column_kwargs={"server_default": func.now()})


def discover_metadata(package: ModuleType) -> MetaData:
    for module in pkgutil.walk_packages(package.__path__, f"{package.__name__}."):
        if module.name.endswith(".models"):
            importlib.import_module(module.name)
    return SQLModel.metadata
