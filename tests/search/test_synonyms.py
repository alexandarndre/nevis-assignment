import pytest
from pydantic import ValidationError

from nevis_search.search.settings import SearchSettings
from nevis_search.search.synonyms import load_synonyms, parse_synonyms


def test_parse_synonyms_normalises_terms() -> None:
    groups = parse_synonyms("Proof of Address,  utility   bill\n\nPassport, ID card\n")
    assert [group.terms for group in groups] == [("proof of address", "utility bill"), ("passport", "id card")]


def test_parse_synonyms_rejects_empty_terms_and_single_term_groups() -> None:
    with pytest.raises(ValidationError):
        parse_synonyms("utility bill,,bank statement")
    with pytest.raises(ValidationError):
        parse_synonyms("lonely term")


def test_shipped_synonyms_link_address_proof_to_utility_bill() -> None:
    groups = load_synonyms(SearchSettings().SYNONYMS_PATH)
    assert any({"address proof", "utility bill"} <= set(group.terms) for group in groups)
