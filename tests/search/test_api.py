import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select

from nevis_search.search.schemas import SEARCH_HITS, ClientHit, DocumentHit, MatchSource, SearchHit
from nevis_search.search.synonyms import load_synonyms
from nevis_search.settings import get_settings
from tests.conftest import Seeded


def search(api: TestClient, q: str, **params: str | int) -> list[SearchHit]:
    response = api.get("/search", params={"q": q, **params})
    assert response.status_code == 200, response.text
    return SEARCH_HITS.validate_json(response.content)


def client_emails(hits: list[SearchHit]) -> list[str]:
    return [hit.client.email for hit in hits if isinstance(hit, ClientHit)]


def document_titles(hits: list[SearchHit]) -> list[str]:
    return [hit.document.title for hit in hits if isinstance(hit, DocumentHit)]


def test_company_name_finds_clients_by_email_domain(api: TestClient, seeded: Seeded) -> None:
    hits = search(api, "NevisWealth")

    assert set(client_emails(hits)) == {"john.doe@neviswealth.com", "sophie.martin@neviswealth.com"}
    assert all(MatchSource.EMAIL in hit.matched_by for hit in hits)


def test_address_proof_finds_the_utility_bill(api: TestClient, seeded: Seeded) -> None:
    hits = search(api, "address proof", type="document")
    utility_bill = next(hit for hit in hits if isinstance(hit, DocumentHit) and "Utility bill" in hit.document.title)

    assert MatchSource.SYNONYM in utility_bill.matched_by
    assert {"Bank statement - Millennium BCP, June 2024", "Tenancy agreement"} <= set(document_titles(hits))
    assert "Passport copy" not in document_titles(hits)


@pytest.mark.parametrize("q", ["Jonh Doe", "Jon Doe", "neviswelth"])
def test_misspelled_names_still_match(api: TestClient, seeded: Seeded, q: str) -> None:
    assert "john.doe@neviswealth.com" in client_emails(search(api, q, type="client"))


def test_description_matches_on_stemmed_words(api: TestClient, seeded: Seeded) -> None:
    hits = search(api, "surgeons", type="client")

    assert client_emails(hits) == ["maria.garcia@example.com"]
    assert hits[0].matched_by == [MatchSource.DESCRIPTION]


def test_semantic_match_without_shared_keywords(api: TestClient, seeded: Seeded) -> None:
    hits = search(api, "selling the company", type="document")

    assert document_titles(hits)[0] == "Share purchase agreement (draft)"
    assert hits[0].matched_by == [MatchSource.SEMANTIC]


def test_keyword_hits_carry_a_highlighted_snippet(api: TestClient, seeded: Seeded) -> None:
    hits = search(api, "gilts", type="document")

    assert isinstance(hits[0], DocumentHit)
    assert hits[0].document.title == "Review meeting notes, 14 May 2024"
    assert "<mark>gilts</mark>" in hits[0].snippet


def test_hits_from_several_retrievers_rank_first(api: TestClient, seeded: Seeded) -> None:
    hits = search(api, "pension")

    assert hits == sorted(hits, key=lambda hit: hit.score, reverse=True)
    assert len(hits[0].matched_by) > 1


def test_minus_is_plain_text_not_a_negation(api: TestClient, seeded: Seeded) -> None:
    hits = search(api, "-pension", type="document")
    keyword_hits = [hit for hit in hits if isinstance(hit, DocumentHit) and MatchSource.KEYWORD in hit.matched_by]

    assert len(keyword_hits) > 0
    assert all("pension" in hit.document.content.lower() for hit in keyword_hits)


def test_no_multi_word_synonym_collapses_to_one_word(db: Engine) -> None:
    with db.connect() as conn:
        collapsed = [
            term
            for group in load_synonyms(get_settings().SYNONYMS_PATH)
            for term in group.terms
            if " " in term
            and conn.execute(select(func.numnode(func.plainto_tsquery("english", term)))).scalar_one() < 3
        ]

    assert collapsed == []


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        ("address", {"Utility bill - British Gas, March 2024", "Tenancy agreement"}),
        ("proof", {"Utility bill - British Gas, March 2024", "Passport copy", "Payslip May 2024"}),
    ],
)
def test_a_word_from_a_synonym_term_expands_its_group(
    api: TestClient, seeded: Seeded, q: str, expected: set[str]
) -> None:
    assert expected <= set(document_titles(search(api, q, type="document")))


def test_stopword_only_query_expands_nothing(api: TestClient, seeded: Seeded) -> None:
    assert search(api, "the of and") == []


def test_unrelated_query_returns_nothing(api: TestClient, seeded: Seeded) -> None:
    assert search(api, "chocolate cake recipe") == []


def test_type_filter(api: TestClient, seeded: Seeded) -> None:
    assert all(isinstance(hit, ClientHit) for hit in search(api, "John Doe", type="client"))
    assert all(isinstance(hit, DocumentHit) for hit in search(api, "John Doe", type="document"))


def test_client_filter_scopes_clients_and_documents(api: TestClient, seeded: Seeded) -> None:
    aisha = seeded.clients["aisha.khan@khanfamilyoffice.co.uk"]

    hits = search(api, "address proof", client_id=str(aisha.id))

    assert document_titles(hits) == ["Tenancy agreement"]
    assert all(hit.document.client_id == aisha.id for hit in hits if isinstance(hit, DocumentHit))


def test_limit_caps_the_number_of_hits(api: TestClient, seeded: Seeded) -> None:
    assert len(search(api, "pension", limit=1)) == 1


@pytest.mark.parametrize(
    "params",
    [{}, {"q": "  "}, {"q": "x" * 257}, {"q": "x", "limit": 0}, {"q": "x", "limit": 51}, {"q": "x", "type": "fund"}],
    ids=["missing-q", "blank-q", "long-q", "limit-0", "limit-51", "bad-type"],
)
def test_invalid_search_parameters_are_422(api: TestClient, params: dict[str, str | int]) -> None:
    assert api.get("/search", params=params).status_code == 422
