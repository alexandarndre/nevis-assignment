import pytest
from pydantic import ValidationError

from nevis_search.search.schemas import SearchParams


def test_search_params_collapse_whitespace() -> None:
    assert SearchParams(q="  address \t proof ").q == "address proof"


@pytest.mark.parametrize("q", ["   ", "a\x00", "x" * 257])
def test_search_params_reject_invalid_queries(q: str) -> None:
    with pytest.raises(ValidationError):
        SearchParams(q=q)
