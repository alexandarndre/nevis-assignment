from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, TypeAdapter
from pydantic import StringConstraints as Str

from nevis_search.clients.schemas import ClientOut
from nevis_search.core.validators import NoNul
from nevis_search.documents.schemas import DocumentOut


class HitType(StrEnum):
    CLIENT = "client"
    DOCUMENT = "document"


class MatchSource(StrEnum):
    NAME = "name"
    EMAIL = "email"
    DESCRIPTION = "description"
    KEYWORD = "keyword"
    SYNONYM = "synonym"
    SEMANTIC = "semantic"


def _collapse_whitespace(value: str) -> str:
    return " ".join(value.split())


class SearchParams(BaseModel):
    q: Annotated[
        str,
        Str(strip_whitespace=True, min_length=1, max_length=256),
        NoNul,
        AfterValidator(_collapse_whitespace),
        Field(
            description="Free-text query matched against clients and documents.",
            examples=["NevisWealth", "address proof", "selling the company"],
        ),
    ]
    type: HitType | None = Field(default=None, description="Restrict results to one kind of hit.")
    client_id: UUID | None = Field(default=None, description="Restrict results to one client and their documents.")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum number of hits returned.")


class BaseHit(BaseModel):
    score: float = Field(description="Reciprocal Rank Fusion score across all retrievers; higher is better.")
    matched_by: list[MatchSource] = Field(description="Retrievers that matched this hit.")


class ClientHit(BaseHit):
    type: Literal[HitType.CLIENT] = HitType.CLIENT
    client: ClientOut


class DocumentHit(BaseHit):
    type: Literal[HitType.DOCUMENT] = HitType.DOCUMENT
    snippet: str = Field(description="HTML-escaped best-matching passage; matched keywords are wrapped in <mark> tags.")
    document: DocumentOut


SearchHit = Annotated[ClientHit | DocumentHit, Field(discriminator="type")]
SEARCH_HITS = TypeAdapter(list[SearchHit])


class Match(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: HitType
    id: UUID
    sources: frozenset[MatchSource]
    snippet: str | None = None


class SearchResponse(BaseModel):
    payload: bytes
    cache_hit: bool
