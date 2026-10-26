from uuid import UUID

from fastapi import APIRouter, Request, Response, status

from nevis_search.core.errors import NotFoundError
from nevis_search.documents import repository
from nevis_search.documents.schemas import DocumentIn, DocumentOut

router = APIRouter()


@router.post(
    "/clients/{id}/documents",
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document for a client",
    description="Stores the document, splits it into passages and indexes them for keyword and semantic search.",
    responses=NotFoundError.documented("Unknown client"),
)
async def create_document(id: UUID, payload: DocumentIn, request: Request, response: Response) -> DocumentOut:
    document = await repository.create_document(id, payload)
    response.headers["Location"] = str(request.app.url_path_for("get_document", id=str(document.id)))
    return document


@router.get(
    "/clients/{id}/documents",
    summary="List a client's documents",
    responses=NotFoundError.documented("Unknown client"),
)
async def list_documents(id: UUID) -> list[DocumentOut]:
    return await repository.list_client_documents(id)


@router.get("/documents/{id}", summary="Get a document", responses=NotFoundError.documented("Unknown document"))
async def get_document(id: UUID) -> DocumentOut:
    return await repository.get_document(id)
