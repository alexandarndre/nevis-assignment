from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response
from pydantic import HttpUrl

from nevis_search.clients.schemas import ClientOut
from nevis_search.core.openapi import Header, SuccessResponse
from nevis_search.documents.schemas import DocumentOut
from nevis_search.search import service
from nevis_search.search.schemas import SEARCH_HITS, ClientHit, DocumentHit, MatchSource, SearchHit, SearchParams

JOHN_DOE = UUID("86e608d1-b0ae-43c6-b497-a438a6403cff")

EXAMPLE_HITS: list[SearchHit] = [
    DocumentHit(
        score=0.016393,
        matched_by=[MatchSource.SYNONYM],
        snippet="British <mark>Gas</mark> <mark>electricity</mark> and <mark>gas</mark> <mark>statement</mark> for",
        document=DocumentOut(
            id=UUID("42f59747-94a8-4841-b796-a13d54e26a2b"),
            client_id=JOHN_DOE,
            title="Utility bill - British Gas, March 2024",
            content="British Gas electricity and gas statement for the billing period 1 to 31 March 2024. ...",
            created_at=datetime(2026, 10, 25, 15, 19, 50, tzinfo=UTC),
        ),
    ),
    ClientHit(
        score=0.016129,
        matched_by=[MatchSource.EMAIL],
        client=ClientOut(
            id=JOHN_DOE,
            first_name="John",
            last_name="Doe",
            email="john.doe@neviswealth.com",
            description="Founder of a fintech start-up. Prefers growth portfolios with an ESG tilt.",
            social_links=[HttpUrl("https://www.linkedin.com/in/johndoe")],
            created_at=datetime(2026, 10, 25, 15, 19, 50, tzinfo=UTC),
        ),
    ),
]

SEARCH_RESPONSE = SuccessResponse(
    description="Hits ordered by score, highest first. Empty when nothing matches.",
    example=SEARCH_HITS.dump_python(EXAMPLE_HITS, mode="json"),
    headers=[
        Header(
            name="X-Cache",
            description="`HIT` when the response was served from Redis, `MISS` when it was computed.",
            values=["HIT", "MISS"],
        )
    ],
)

router = APIRouter()


@router.get(
    "",
    name="search",
    summary="Search clients and documents",
    description=(
        "Hybrid search. Clients match on name and email (trigram, typo tolerant) and on description "
        "(full text). Documents match on keywords (full text), on domain synonyms (e.g. *address proof* "
        "also finds *utility bill*) and semantically (vector similarity over passages). The rankings are "
        "merged with Reciprocal Rank Fusion."
    ),
    response_model=list[SearchHit],
    responses=SEARCH_RESPONSE.documented(),
)
async def search_endpoint(params: Annotated[SearchParams, Query()]) -> Response:
    result = await service.search(params)
    return Response(
        content=result.payload,
        media_type="application/json",
        headers={"X-Cache": "HIT" if result.cache_hit else "MISS"},
    )
