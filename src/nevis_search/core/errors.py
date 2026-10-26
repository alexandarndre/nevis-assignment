from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel


class ErrorOut(BaseModel):
    detail: str


type ResponseDocs = dict[int | str, dict[str, type[ErrorOut] | str]]


class ServiceError(Exception):
    status_code: ClassVar[int]

    @classmethod
    def documented(cls, description: str) -> ResponseDocs:
        return {cls.status_code: {"model": ErrorOut, "description": description}}


class NotFoundError(ServiceError):
    status_code = 404

    def __init__(self, entity: str, entity_id: UUID) -> None:
        super().__init__(f"{entity} {entity_id} not found")


class ConflictError(ServiceError):
    status_code = 409


class UpstreamError(ServiceError):
    status_code = 502


class UnavailableError(ServiceError):
    status_code = 503
