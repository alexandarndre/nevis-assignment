from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class SummaryMethod(StrEnum):
    LLM = "llm"
    EXTRACTIVE = "extractive"


class SummaryResult(BaseModel):
    summary: str
    method: SummaryMethod
    model: str = Field(description="LLM used, or the embedding model behind the extractive summary.")


class DocumentSummary(SummaryResult):
    document_id: UUID
