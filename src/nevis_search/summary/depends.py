from functools import lru_cache
from typing import Annotated

from anthropic import AsyncAnthropic
from fastapi import Depends

from nevis_search.embeddings.service import load_embedder
from nevis_search.settings import get_settings
from nevis_search.summary.service import ClaudeSummarizer, ExtractiveSummarizer, Summarizer


@lru_cache
def get_summarizer() -> Summarizer:
    settings = get_settings()
    extractive = ExtractiveSummarizer(load_embedder(settings), settings.SUMMARY_SENTENCES)
    if settings.ANTHROPIC_API_KEY is None:
        return extractive
    return ClaudeSummarizer(
        AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY.get_secret_value()), settings.SUMMARY_MODEL, extractive
    )


SummarizerDep = Annotated[Summarizer, Depends(get_summarizer)]
