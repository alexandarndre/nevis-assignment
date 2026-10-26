from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints


class SynonymGroup(BaseModel):
    terms: tuple[Annotated[str, StringConstraints(min_length=1)], ...] = Field(min_length=2)


def parse_synonyms(text: str) -> tuple[SynonymGroup, ...]:
    return tuple(
        SynonymGroup(terms=tuple(" ".join(term.lower().split()) for term in line.split(",")))
        for line in text.splitlines()
        if line.strip() != ""
    )


@lru_cache
def load_synonyms(path: Path) -> tuple[SynonymGroup, ...]:
    return parse_synonyms(path.read_text(encoding="utf-8"))
