from uuid import UUID

from fastapi import APIRouter

from nevis_search.core.errors import NotFoundError, UpstreamError
from nevis_search.summary.depends import SummarizerDep
from nevis_search.summary.schemas import DocumentSummary
from nevis_search.summary.service import summarize_document

router = APIRouter()


@router.get(
    "/{id}/summary",
    summary="Summarize a document",
    description=(
        "Summarizes with Claude when `ANTHROPIC_API_KEY` is configured, otherwise picks the sentences closest "
        "to the document's embedding centroid. Results are cached in Redis by content hash."
    ),
    responses=NotFoundError.documented("Unknown document") | UpstreamError.documented("LLM provider failed"),
)
async def get_document_summary(id: UUID, summarizer: SummarizerDep) -> DocumentSummary:
    return await summarize_document(id, summarizer)
