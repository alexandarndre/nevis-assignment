from collections import defaultdict
from collections.abc import Iterable, Sequence
from itertools import chain
from uuid import UUID

from pydantic import BaseModel

from nevis_search.search.schemas import HitType, Match, MatchSource

type HitKey = tuple[HitType, UUID]


class Fused(BaseModel):
    ranked: list[HitKey]
    scores: dict[HitKey, float]
    sources: dict[HitKey, list[MatchSource]]
    snippets: dict[UUID, str]


def reciprocal_rank_fusion[K](rankings: Iterable[Sequence[K]], k: int) -> dict[K, float]:
    scores: defaultdict[K, float] = defaultdict(float)
    for ranking in rankings:
        for rank, key in enumerate(ranking, start=1):
            scores[key] += 1 / (k + rank)
    return dict(scores)


def fuse(rankings: Sequence[Sequence[Match]], k: int, limit: int) -> Fused:
    scores = reciprocal_rank_fusion([[(match.kind, match.id) for match in ranking] for ranking in rankings], k)
    sources: defaultdict[HitKey, set[MatchSource]] = defaultdict(set)
    snippets: dict[UUID, str] = {}
    for match in chain.from_iterable(rankings):
        sources[(match.kind, match.id)] |= match.sources
        if match.snippet is not None:
            snippets[match.id] = match.snippet
    return Fused(
        ranked=sorted(scores, key=lambda key: (-scores[key], str(key[1])))[:limit],
        scores=scores,
        sources={key: [source for source in MatchSource if source in found] for key, found in sources.items()},
        snippets=snippets,
    )


def client_fields(name_similarity: float, email_similarity: float, threshold: float) -> frozenset[MatchSource]:
    similarities = {MatchSource.NAME: name_similarity, MatchSource.EMAIL: email_similarity}
    matched = frozenset(source for source, value in similarities.items() if value >= threshold)
    return matched if len(matched) > 0 else frozenset({max(similarities, key=similarities.__getitem__)})
