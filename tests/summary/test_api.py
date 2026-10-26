from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from nevis_search.core.errors import UpstreamError
from nevis_search.summary.depends import get_summarizer
from nevis_search.summary.schemas import SummaryMethod, SummaryResult
from tests.summary.test_service import MEETING_NOTES


class CountingSummarizer:
    def __init__(self) -> None:
        self.calls = 0

    @property
    def model(self) -> str:
        return "fake-model"

    async def summarize(self, title: str, content: str) -> SummaryResult:
        self.calls += 1
        return SummaryResult(summary=f"{title}: {len(content)} chars", method=SummaryMethod.LLM, model=self.model)


class FailingSummarizer(CountingSummarizer):
    async def summarize(self, title: str, content: str) -> SummaryResult:
        raise UpstreamError("summary provider failed: overloaded")


@pytest.fixture
def document_id(client: TestClient) -> str:
    owner = client.post("/clients", json={"first_name": "Ann", "last_name": "Lee", "email": "ann@example.com"}).json()
    response = client.post(f"/clients/{owner['id']}/documents", json={"title": "Review", "content": MEETING_NOTES})
    return str(response.json()["id"])


def test_summary_endpoint_defaults_to_extractive(client: TestClient, document_id: str) -> None:
    response = client.get(f"/documents/{document_id}/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["document_id"] == document_id
    assert body["method"] == "extractive"
    assert body["model"] == "BAAI/bge-small-en-v1.5"


def test_summary_is_cached_by_content(client: TestClient, app: FastAPI, document_id: str) -> None:
    summarizer = CountingSummarizer()
    app.dependency_overrides[get_summarizer] = lambda: summarizer

    first = client.get(f"/documents/{document_id}/summary").json()
    second = client.get(f"/documents/{document_id}/summary").json()

    assert first == second
    assert first["summary"] == f"Review: {len(MEETING_NOTES)} chars"
    assert summarizer.calls == 1


def test_llm_failure_is_502(client: TestClient, app: FastAPI, document_id: str) -> None:
    app.dependency_overrides[get_summarizer] = FailingSummarizer

    response = client.get(f"/documents/{document_id}/summary")

    assert response.status_code == 502
    assert response.json() == {"detail": "summary provider failed: overloaded"}


def test_summary_of_unknown_document_is_404(client: TestClient) -> None:
    assert client.get(f"/documents/{uuid4()}/summary").status_code == 404
