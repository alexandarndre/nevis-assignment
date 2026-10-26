from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

type Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]
type HealthCheck = Callable[[], Awaitable[None]]


class Tag(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    description: str


class Route(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    router: APIRouter
    prefix: str
    tag: Tag


class SwaggerUI(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    try_it_out_enabled: bool = True
    display_request_duration: bool = True


class App(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    title: str
    version: str
    description: str
    api_prefix: str
    routes: list[Route]
    healthchecks: list[HealthCheck] = Field(default_factory=list)
    lifespans: list[Lifespan] = Field(default_factory=list)
    swagger_ui: SwaggerUI = Field(default_factory=SwaggerUI)

    def tags(self) -> list[Tag]:
        return list(dict.fromkeys(route.tag for route in self.routes))
