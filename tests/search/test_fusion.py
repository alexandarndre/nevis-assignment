from uuid import uuid4

import pytest

from nevis_search.search.fusion import client_fields, fuse, reciprocal_rank_fusion
from nevis_search.search.schemas import HitType, Match, MatchSource


def test_rrf_rewards_agreement_between_rankings() -> None:
    scores = reciprocal_rank_fusion([["a", "b", "c"], ["b", "a"], ["b"]], k=60)
    assert max(scores, key=scores.__getitem__) == "b"
    assert scores["c"] == pytest.approx(1 / 63)


def test_rrf_of_no_rankings_is_empty() -> None:
    assert reciprocal_rank_fusion([], k=60) == {}


def test_fuse_merges_sources_keeps_snippets_and_limits() -> None:
    shared, other = uuid4(), uuid4()
    keyword = [Match(kind=HitType.DOCUMENT, id=shared, sources=frozenset({MatchSource.KEYWORD}))]
    semantic = [
        Match(kind=HitType.DOCUMENT, id=other, sources=frozenset({MatchSource.SEMANTIC}), snippet="other"),
        Match(kind=HitType.DOCUMENT, id=shared, sources=frozenset({MatchSource.SEMANTIC}), snippet="shared"),
    ]

    fused = fuse([keyword, semantic], k=60, limit=1)

    assert fused.ranked == [(HitType.DOCUMENT, shared)]
    assert fused.sources[(HitType.DOCUMENT, shared)] == [MatchSource.KEYWORD, MatchSource.SEMANTIC]
    assert fused.snippets == {other: "other", shared: "shared"}


def test_client_fields_reports_every_field_over_threshold() -> None:
    assert client_fields(0.9, 0.7, threshold=0.5) == {MatchSource.NAME, MatchSource.EMAIL}


def test_client_fields_falls_back_to_the_closest_field() -> None:
    assert client_fields(0.2, 0.4, threshold=0.5) == {MatchSource.EMAIL}
