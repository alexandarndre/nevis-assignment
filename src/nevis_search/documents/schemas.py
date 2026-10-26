from typing import Annotated
from uuid import UUID

from pydantic import StringConstraints as Str
from sqlalchemy import Text
from sqlmodel import Field, SQLModel

from nevis_search.core.db.models import Record
from nevis_search.core.validators import NoNul


class DocumentBase(SQLModel):
    title: Annotated[str, Str(strip_whitespace=True, min_length=1, max_length=300), NoNul] = Field(sa_type=Text)
    content: Annotated[str, Str(strip_whitespace=True, min_length=1, max_length=200_000), NoNul] = Field(sa_type=Text)


class DocumentIn(DocumentBase):
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "title": "Utility bill - March 2024",
                    "content": "British Gas electricity statement for 12 Baker Street, London. Amount due 84.20 GBP.",
                }
            ]
        }
    }


class DocumentOut(DocumentBase, Record):
    client_id: UUID
