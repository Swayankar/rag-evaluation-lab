"""
Every retrieval strategy (plain vector search, BM25, hybrid, reranked)
implements this interface so RAGPipeline and the API layer never need
to know which one is in play — they just call .retrieve(query, top_k).
"""
from abc import ABC, abstractmethod

from app.models.query import RetrievedChunk


class BaseRetriever(ABC):
    @abstractmethod
    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        raise NotImplementedError
