import asyncio
from typing import Protocol
from uuid import UUID

import anthropic
import numpy as np
from anthropic import AsyncAnthropic
from anthropic.types import Message

from nevis_search.core.cache.lifehooks import get_cache
from nevis_search.core.errors import UpstreamError
from nevis_search.documents.chunking import split_sentences
from nevis_search.documents.repository import get_document
from nevis_search.embeddings.service import Embedder
from nevis_search.settings import get_settings
from nevis_search.summary.schemas import DocumentSummary, SummaryMethod, SummaryResult

SUMMARY_SYSTEM_PROMPT = (
    "You summarize client documents for a wealth advisor. Write two or three plain sentences: "
    "what kind of document it is, then the facts an advisor acts on (people, dates, amounts, obligations). "
    "Use only what the document states. No preamble, headings or bullet points."
)


class Summarizer(Protocol):
    @property
    def model(self) -> str: ...

    async def summarize(self, title: str, content: str) -> SummaryResult: ...


class ExtractiveSummarizer:
    def __init__(self, embedder: Embedder, sentences: int) -> None:
        self._embedder = embedder
        self._sentences = sentences

    @property
    def model(self) -> str:
        return self._embedder.model_name

    async def summarize(self, title: str, content: str) -> SummaryResult:
        sentences = split_sentences(content)
        if len(sentences) > self._sentences:
            vectors = np.stack(await asyncio.to_thread(self._embedder.embed_passages, sentences))
            centroid = vectors.mean(axis=0)
            scores = vectors @ centroid / (np.linalg.norm(vectors, axis=1) * np.linalg.norm(centroid))
            sentences = [sentences[i] for i in sorted(np.argsort(-scores)[: self._sentences])]
        return SummaryResult(summary=" ".join(sentences), method=SummaryMethod.EXTRACTIVE, model=self.model)


class ClaudeSummarizer:
    def __init__(self, client: AsyncAnthropic, model: str, fallback: ExtractiveSummarizer) -> None:
        self._client = client
        self._model = model
        self._fallback = fallback

    @property
    def model(self) -> str:
        return self._model

    async def summarize(self, title: str, content: str) -> SummaryResult:
        try:
            message = await self._client.messages.create(
                model=self._model,
                max_tokens=16000,
                output_config={"effort": "low"},
                system=SUMMARY_SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": f"<title>{title}</title>\n<document>\n{content}\n</document>",
                    }
                ],
            )
        except anthropic.APIError as exc:
            raise UpstreamError(f"summary provider failed: {exc}") from exc
        if message.stop_reason == "refusal":
            return await self._fallback.summarize(title, content)
        return SummaryResult(summary=message_text(message), method=SummaryMethod.LLM, model=self._model)


def message_text(message: Message) -> str:
    if message.stop_reason != "end_turn":
        raise UpstreamError(f"summary generation stopped early: {message.stop_reason}")
    return "".join(block.text for block in message.content if block.type == "text").strip()


async def summarize_document(document_id: UUID, summarizer: Summarizer) -> DocumentSummary:
    settings = get_settings()
    cache = get_cache(settings.REDIS_URL, settings.REDIS_KEY_PREFIX)
    document = await get_document(document_id)
    key = cache.key("summary", summarizer.model, document.title, document.content)
    cached = await cache.get(key)
    if cached is not None:
        result = SummaryResult.model_validate_json(cached)
    else:
        result = await summarizer.summarize(document.title, document.content)
        await cache.set(key, result.model_dump_json().encode(), settings.SUMMARY_CACHE_TTL_SECONDS)
    return DocumentSummary(document_id=document.id, **result.model_dump())
