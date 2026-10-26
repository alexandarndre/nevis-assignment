from uuid import UUID

from fastapi import APIRouter, Request, Response, status

from nevis_search.clients import repository
from nevis_search.clients.schemas import ClientIn, ClientOut
from nevis_search.core.errors import ConflictError, NotFoundError

router = APIRouter()


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a client",
    responses=ConflictError.documented("Email already registered"),
)
async def create_client(payload: ClientIn, request: Request, response: Response) -> ClientOut:
    client = await repository.create_client(payload)
    response.headers["Location"] = str(request.app.url_path_for("get_client", id=str(client.id)))
    return client


@router.get("/{id}", summary="Get a client", responses=NotFoundError.documented("Unknown client"))
async def get_client(id: UUID) -> ClientOut:
    return await repository.get_client(id)
