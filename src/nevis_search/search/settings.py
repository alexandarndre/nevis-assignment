from pathlib import Path

from pydantic import BaseModel, Field


class SearchSettings(BaseModel):
    CLIENT_MATCH_THRESHOLD: float = Field(default=0.5, gt=0, le=1)
    SEMANTIC_MIN_SIMILARITY: float = Field(default=0.6, gt=0, le=1)
    RETRIEVER_DEPTH: int = Field(default=50, ge=1)
    RRF_K: int = Field(default=60, ge=1)
    SYNONYMS_PATH: Path = Path(__file__).with_name("synonyms.txt")
    SEARCH_CACHE_TTL_SECONDS: int = Field(default=300, ge=1)
