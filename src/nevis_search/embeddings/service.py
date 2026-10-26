from functools import lru_cache
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding
from numpy.typing import NDArray

from nevis_search.embeddings.constants import EMBEDDING_DIM
from nevis_search.embeddings.settings import EmbeddingSettings

type Vector = NDArray[np.float32]


class Embedder:
    def __init__(self, model_name: str, cache_dir: Path | None) -> None:
        self.model_name = model_name
        self._model = TextEmbedding(model_name, cache_dir=None if cache_dir is None else str(cache_dir))
        if self._model.embedding_size != EMBEDDING_DIM:
            raise ValueError(
                f"{model_name} produces {self._model.embedding_size}-d vectors, schema expects {EMBEDDING_DIM}"
            )

    def embed_query(self, text: str) -> Vector:
        return np.asarray(next(iter(self._model.query_embed(text))), dtype=np.float32)

    def embed_passages(self, texts: list[str]) -> list[Vector]:
        return [np.asarray(vector, dtype=np.float32) for vector in self._model.passage_embed(texts)]


@lru_cache
def get_embedder(model_name: str, cache_dir: Path | None) -> Embedder:
    return Embedder(model_name, cache_dir)


def load_embedder(settings: EmbeddingSettings) -> Embedder:
    return get_embedder(settings.EMBEDDING_MODEL, settings.EMBEDDING_CACHE_DIR)
