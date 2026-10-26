from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

JOHN = {"first_name": "John", "last_name": "Doe", "email": "john.doe@neviswealth.com"}


def test_create_client_returns_201_location_and_defaults(client: TestClient) -> None:
    response = client.post("/clients", json={**JOHN, "first_name": "  John "})

    assert response.status_code == 201
    body = response.json()
    assert response.headers["location"] == f"/api/v1/clients/{body['id']}"
    assert body["first_name"] == "John"
    assert body["description"] is None
    assert body["social_links"] == []
    assert body["created_at"].endswith("Z") or "+00:00" in body["created_at"]


def test_create_client_round_trips_optional_fields(client: TestClient) -> None:
    payload = {
        **JOHN,
        "description": "Prefers ESG funds",
        "social_links": ["https://www.linkedin.com/in/johndoe"],
    }
    created = client.post("/clients", json=payload).json()

    fetched = client.get(f"/clients/{created['id']}")

    assert fetched.status_code == 200
    assert fetched.json() == created
    assert created["description"] == "Prefers ESG funds"
    assert created["social_links"] == ["https://www.linkedin.com/in/johndoe"]


def test_duplicate_email_is_a_conflict_regardless_of_case(client: TestClient) -> None:
    assert client.post("/clients", json=JOHN).status_code == 201

    response = client.post("/clients", json={**JOHN, "email": "John.Doe@NevisWealth.com"})

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


@pytest.mark.parametrize(
    "payload",
    [
        {**JOHN, "email": "not-an-email"},
        {**JOHN, "first_name": "   "},
        {"first_name": "John", "last_name": "Doe"},
        {**JOHN, "social_links": ["not a url"]},
        {**JOHN, "description": "x" * 5001},
    ],
    ids=["bad-email", "blank-name", "missing-email", "bad-link", "long-description"],
)
def test_invalid_client_payloads_are_422(client: TestClient, payload: dict[str, str | list[str]]) -> None:
    assert client.post("/clients", json=payload).status_code == 422


def test_unknown_client_is_404(client: TestClient) -> None:
    response = client.get(f"/clients/{uuid4()}")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_malformed_client_id_is_422(client: TestClient) -> None:
    assert client.get("/clients/not-a-uuid").status_code == 422
