from pathlib import Path

from pydantic import BaseModel, Field


class EmbeddingSettings(BaseModel):
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_CACHE_DIR: Path | None = None
    EMBEDDING_CACHE_TTL_SECONDS: int = Field(default=7 * 24 * 3600, ge=1)
    CHUNK_MAX_WORDS: int = Field(default=120, ge=20)
