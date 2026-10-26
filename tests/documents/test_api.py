from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlmodel import col

from nevis_search.documents.models import DocumentChunk
from nevis_search.search.schemas import SEARCH_HITS, DocumentHit

UTILITY_BILL = {"title": "Utility bill", "content": "Electricity bill for 12 Baker Street, London."}


@pytest.fixture
def client_id(client: TestClient) -> str:
    response = client.post("/clients", json={"first_name": "Ann", "last_name": "Lee", "email": "ann@example.com"})
    return str(response.json()["id"])


def test_create_document_returns_201_location_and_spec_fields(client: TestClient, client_id: str) -> None:
    response = client.post(f"/clients/{client_id}/documents", json=UTILITY_BILL)

    assert response.status_code == 201
    body = response.json()
    assert response.headers["location"] == f"/api/v1/documents/{body['id']}"
    assert set(body) == {"id", "client_id", "title", "content", "created_at"}
    assert body["client_id"] == client_id
    assert client.get(f"/documents/{body['id']}").json() == body


def test_document_for_unknown_client_is_404(client: TestClient) -> None:
    response = client.post(f"/clients/{uuid4()}/documents", json=UTILITY_BILL)

    assert response.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [{"title": "", "content": "x"}, {"title": "x", "content": "   "}, {"title": "x"}, {"content": "x"}],
    ids=["empty-title", "blank-content", "missing-content", "missing-title"],
)
def test_invalid_document_payloads_are_422(client: TestClient, client_id: str, payload: dict[str, str]) -> None:
    assert client.post(f"/clients/{client_id}/documents", json=payload).status_code == 422


def test_long_document_is_indexed_as_several_passages(client: TestClient, client_id: str, db: Engine) -> None:
    content = " ".join(f"Paragraph {i} discusses portfolio rebalancing and fees in detail." for i in range(60))

    document_id = client.post(f"/clients/{client_id}/documents", json={"title": "Long", "content": content}).json()[
        "id"
    ]

    with db.connect() as conn:
        chunks = conn.execute(
            select(func.count()).select_from(DocumentChunk).where(col(DocumentChunk.document_id) == document_id)
        ).scalar_one()
    assert chunks > 1


def test_list_documents_is_newest_first(client: TestClient, client_id: str) -> None:
    first = client.post(f"/clients/{client_id}/documents", json=UTILITY_BILL).json()
    second = client.post(f"/clients/{client_id}/documents", json={**UTILITY_BILL, "title": "Second"}).json()

    response = client.get(f"/clients/{client_id}/documents")

    assert response.status_code == 200
    assert [document["id"] for document in response.json()] == [second["id"], first["id"]]


def test_list_documents_of_unknown_client_is_404(client: TestClient) -> None:
    assert client.get(f"/clients/{uuid4()}/documents").status_code == 404


def test_unknown_document_is_404(client: TestClient) -> None:
    assert client.get(f"/documents/{uuid4()}").status_code == 404


def test_search_snippets_never_echo_document_html(client: TestClient, client_id: str) -> None:
    client.post(
        f"/clients/{client_id}/documents",
        json={"title": "Invoice", "content": "Invoice <img src=x onerror=alert(1)> \u27e7 for advisory fees."},
    )

    hits = SEARCH_HITS.validate_json(client.get("/search", params={"q": "invoice", "type": "document"}).content)

    assert isinstance(hits[0], DocumentHit)
    assert "<img" not in hits[0].snippet
    assert "&lt;img" in hits[0].snippet
    assert "<mark>Invoice</mark>" in hits[0].snippet
    assert hits[0].snippet.count("<mark>") == hits[0].snippet.count("</mark>")


def test_nul_characters_are_rejected(client: TestClient, client_id: str) -> None:
    response = client.post(f"/clients/{client_id}/documents", json={"title": "x", "content": "bad\u0000byte"})

    assert response.status_code == 422
    assert client.get("/search", params={"q": "a\u0000"}).status_code == 422
