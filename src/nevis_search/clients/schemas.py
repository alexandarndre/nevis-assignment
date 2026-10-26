from typing import Annotated

from pydantic import EmailStr, HttpUrl
from pydantic import StringConstraints as Str
from sqlalchemy import Text, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, SQLModel

from nevis_search.core.db.models import Record
from nevis_search.core.validators import NoNul


class ClientBase(SQLModel):
    first_name: Annotated[str, Str(strip_whitespace=True, min_length=1, max_length=100), NoNul] = Field(sa_type=Text)
    last_name: Annotated[str, Str(strip_whitespace=True, min_length=1, max_length=100), NoNul] = Field(sa_type=Text)
    email: EmailStr = Field(sa_type=Text)
    description: Annotated[str, Str(strip_whitespace=True, max_length=5000), NoNul] | None = Field(
        default=None, sa_type=Text
    )
    social_links: list[HttpUrl] = Field(
        default_factory=list, max_length=20, sa_type=ARRAY(Text), sa_column_kwargs={"server_default": text("'{}'")}
    )


class ClientIn(ClientBase):
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "first_name": "John",
                    "last_name": "Doe",
                    "email": "john.doe@neviswealth.com",
                    "description": "Founder of a fintech start-up, focused on long-term growth.",
                    "social_links": ["https://www.linkedin.com/in/johndoe"],
                }
            ]
        }
    }


class ClientOut(ClientBase, Record):
    pass
