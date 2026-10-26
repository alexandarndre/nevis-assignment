import json

import anthropic
import httpx2
import pytest
from anthropic.types import Message, StopReason

from nevis_search.core.errors import UpstreamError
from nevis_search.embeddings.service import Embedder, load_embedder
from nevis_search.settings import Settings
from nevis_search.summary.schemas import SummaryMethod, SummaryResult
from nevis_search.summary.service import ClaudeSummarizer, ExtractiveSummarizer

MEETING_NOTES = (
    "The client wants to retire at 60. She holds 400,000 GBP in a SIPP and 150,000 GBP in ISAs. "
    "We discussed moving 40% of the portfolio into short-dated gilts. The weather was nice. "
    "The next review is scheduled for November."
)


@pytest.fixture(scope="module")
def embedder() -> Embedder:
    return load_embedder(Settings())


def claude_reply(stop_reason: StopReason, text: str) -> Message:
    return Message.model_validate(
        {
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "model": "claude-haiku-5-5",
            "content": [{"type": "text", "text": text}],
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
    )


def claude_summarizer(
    embedder: Embedder, respond: httpx2.Response, requests: list[httpx2.Request] | None = None
) -> ClaudeSummarizer:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if requests is not None:
            requests.append(request)
        return respond

    client = anthropic.AsyncAnthropic(
        api_key="test",
        max_retries=0,
        http_client=anthropic.DefaultAsyncHttpxClient(transport=httpx2.MockTransport(handler)),
    )
    return ClaudeSummarizer(client, "claude-haiku-5-5", ExtractiveSummarizer(embedder, sentences=2))


def ok(stop_reason: StopReason, text: str) -> httpx2.Response:
    return httpx2.Response(200, json=claude_reply(stop_reason, text).model_dump(mode="json"))


async def test_extractive_summary_keeps_central_sentences_in_order(embedder: Embedder) -> None:
    result = await ExtractiveSummarizer(embedder, sentences=2).summarize("Review", MEETING_NOTES)

    sentences = result.summary.split(". ")
    assert len(sentences) == 2
    assert "weather" not in result.summary
    assert MEETING_NOTES.index(sentences[0]) < MEETING_NOTES.index(sentences[1].rstrip("."))
    assert result.method is SummaryMethod.EXTRACTIVE


async def test_extractive_summary_of_short_text_is_the_text(embedder: Embedder) -> None:
    result = await ExtractiveSummarizer(embedder, sentences=3).summarize("Note", "Call the client.")

    assert result.summary == "Call the client."


async def test_claude_summarizer_sends_the_document_and_returns_the_text(embedder: Embedder) -> None:
    requests: list[httpx2.Request] = []

    result = await claude_summarizer(embedder, ok("end_turn", "A meeting note."), requests).summarize(
        "Review", MEETING_NOTES
    )

    body = json.loads(requests[0].content)
    assert result == SummaryResult(summary="A meeting note.", method=SummaryMethod.LLM, model="claude-haiku-5-5")
    assert body["model"] == "claude-haiku-5-5"
    assert body["output_config"] == {"effort": "low"}
    assert MEETING_NOTES in body["messages"][0]["content"]


async def test_claude_refusal_falls_back_to_extractive(embedder: Embedder) -> None:
    result = await claude_summarizer(embedder, ok("refusal", "")).summarize("Review", MEETING_NOTES)

    assert result.method is SummaryMethod.EXTRACTIVE


async def test_claude_truncated_answer_is_an_upstream_error(embedder: Embedder) -> None:
    with pytest.raises(UpstreamError, match="max_tokens"):
        await claude_summarizer(embedder, ok("max_tokens", "A meet")).summarize("Review", MEETING_NOTES)


async def test_claude_api_failure_is_an_upstream_error(embedder: Embedder) -> None:
    overloaded = httpx2.Response(529, json={"type": "error", "error": {"type": "overloaded_error", "message": "busy"}})

    with pytest.raises(UpstreamError, match="summary provider failed"):
        await claude_summarizer(embedder, overloaded).summarize("Review", MEETING_NOTES)
