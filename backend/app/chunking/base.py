"""
Every chunking strategy (fixed, semantic, ...) implements this interface
so the rest of the pipeline (retrieval, evaluation) never needs to know
which one produced a given Chunk.
"""
from abc import ABC, abstractmethod

from app.models.document import Chunk, RawPage


class BaseChunker(ABC):
    strategy_name: str = "base"

    @abstractmethod
    def chunk_pages(self, pages: list[RawPage]) -> list[Chunk]:
        """Turn a document's raw pages into a list of Chunks."""
        raise NotImplementedError
