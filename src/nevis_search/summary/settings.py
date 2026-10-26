from pydantic import BaseModel, Field, SecretStr


class SummarySettings(BaseModel):
    ANTHROPIC_API_KEY: SecretStr | None = None
    SUMMARY_MODEL: str = "claude-haiku-5-5"
    SUMMARY_SENTENCES: int = Field(default=3, ge=1)
    SUMMARY_CACHE_TTL_SECONDS: int = Field(default=30 * 24 * 3600, ge=1)
