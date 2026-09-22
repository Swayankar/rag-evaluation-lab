"""
Turns chunk text into vectors.

Two backends:
  - SentenceTransformerEmbedder: real semantic embeddings (all-MiniLM-L6-v2
    by default). This is what you want for actual retrieval quality.
  - HashingEmbedder: a dependency-free, deterministic bag-of-words hash
    embedding. Not semantically meaningful, but lets the whole pipeline
    run offline / without a model download — used automatically if
    sentence-transformers isn't installed or its model can't be fetched,
    same resilience pattern as the tiktoken fallback in Phase 1.

get_embedder() picks the right one based on settings and falls back
automatically, logging a warning when it does.
"""
import hashlib
from abc import ABC, abstractmethod

import numpy as np

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class BaseEmbedder(ABC):
    dimension: int

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> np.ndarray:
        """Returns an (len(texts), dimension) float32 array."""
        raise NotImplementedError

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed_texts([text])[0]


class HashingEmbedder(BaseEmbedder):

    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        vectors = np.zeros((len(texts), self.dimension), dtype=np.float32)
        for i, text in enumerate(texts):
            for word in text.lower().split():
                idx = int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dimension
                vectors[i, idx] += 1.0
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vectors / norms


class SentenceTransformerEmbedder(BaseEmbedder):
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer  # lazy import

        logger.info("Loading sentence-transformers model: %s", model_name)
        self._model = SentenceTransformer(model_name)
        self.dimension = self._model.get_sentence_embedding_dimension()

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        embeddings = self._model.encode(
            texts, normalize_embeddings=True, show_progress_bar=False
        )
        return np.asarray(embeddings, dtype=np.float32)


def get_embedder(settings: Settings | None = None) -> BaseEmbedder:
    settings = settings or get_settings()

    if settings.embedding_backend == "hashing":
        return HashingEmbedder()

    try:
        return SentenceTransformerEmbedder(settings.embedding_model_name)
    except Exception as exc:  # noqa: BLE001 - deliberate broad fallback
        logger.warning(
            "Falling back to HashingEmbedder — sentence-transformers unavailable "
            "(%s). Install it with `pip install -e \".[embeddings]\"` for real "
            "semantic embeddings.",
            exc,
        )
        return HashingEmbedder()
