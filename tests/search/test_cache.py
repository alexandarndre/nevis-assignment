from fastapi.testclient import TestClient

from nevis_search.search.schemas import SEARCH_HITS, DocumentHit


def test_repeated_search_is_served_from_cache(client: TestClient) -> None:
    client.post("/clients", json={"first_name": "Ann", "last_name": "Lee", "email": "ann@example.com"})

    first = client.get("/search", params={"q": "Ann Lee"})
    second = client.get("/search", params={"q": "  Ann   Lee "})

    assert first.headers["x-cache"] == "MISS"
    assert second.headers["x-cache"] == "HIT"
    assert first.content == second.content


def test_writes_invalidate_cached_searches(client: TestClient) -> None:
    ann = client.post("/clients", json={"first_name": "Ann", "last_name": "Lee", "email": "ann@example.com"}).json()
    assert client.get("/search", params={"q": "tenancy agreement"}).json() == []

    client.post(
        f"/clients/{ann['id']}/documents",
        json={"title": "Tenancy agreement", "content": "Lease of Flat 2 for twelve months."},
    )
    response = client.get("/search", params={"q": "tenancy agreement"})

    assert response.headers["x-cache"] == "MISS"
    hits = SEARCH_HITS.validate_json(response.content)
    assert [hit.document.title for hit in hits if isinstance(hit, DocumentHit)] == ["Tenancy agreement"]
