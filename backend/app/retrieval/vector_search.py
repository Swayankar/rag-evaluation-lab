import json
from pathlib import Path

import numpy as np

from app.core.logging import get_logger
from app.models.document import Chunk

logger = get_logger(__name__)

_EMBEDDINGS_FILE = "embeddings.npy"
_CHUNKS_FILE = "chunks.json"


class VectorStore:
    def __init__(self) -> None:
        self._embeddings: np.ndarray | None = None
        self._chunks: list[Chunk] = []

    def build(self, chunks: list[Chunk], embeddings: np.ndarray) -> None:
        if len(chunks) != embeddings.shape[0]:
            raise ValueError(
                f"chunk count ({len(chunks)}) != embedding count ({embeddings.shape[0]})"
            )
        self._chunks = chunks
        self._embeddings = embeddings.astype(np.float32)

    def save(self, directory: Path) -> None:
        if self._embeddings is None:
            raise RuntimeError("Nothing to save — call build() first")
        directory.mkdir(parents=True, exist_ok=True)
        np.save(directory / _EMBEDDINGS_FILE, self._embeddings)
        with (directory / _CHUNKS_FILE).open("w", encoding="utf-8") as f:
            json.dump([c.model_dump() for c in self._chunks], f, ensure_ascii=False)
        logger.info(
            "Saved vector store to %s (%d vectors, dim=%d)",
            directory,
            len(self._chunks),
            self._embeddings.shape[1],
        )

    @classmethod
    def load(cls, directory: Path) -> "VectorStore":
        store = cls()
        store._embeddings = np.load(directory / _EMBEDDINGS_FILE)
        with (directory / _CHUNKS_FILE).open("r", encoding="utf-8") as f:
            data = json.load(f)
        store._chunks = [Chunk(**d) for d in data]
        return store

    def search(self, query_embedding: np.ndarray, top_k: int = 5) -> list[tuple[Chunk, float]]:
        """Cosine similarity search. Assumes stored embeddings are already
        normalized (both embedder backends normalize); the query vector is
        normalized defensively here regardless."""
        if self._embeddings is None or len(self._chunks) == 0:
            return []

        norm = np.linalg.norm(query_embedding)
        q = query_embedding / norm if norm > 0 else query_embedding

        scores = self._embeddings @ q
        k = min(top_k, len(scores))
        top_indices = np.argsort(-scores)[:k]
        return [(self._chunks[i], float(scores[i])) for i in top_indices]

    def __len__(self) -> int:
        return len(self._chunks)
