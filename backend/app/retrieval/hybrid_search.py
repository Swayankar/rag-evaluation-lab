from app.core.logging import get_logger
from app.models.query import RetrievedChunk
from app.retrieval.base import BaseRetriever

logger = get_logger(__name__)


class HybridRetriever(BaseRetriever):
    def __init__(
        self,
        vector_retriever: BaseRetriever,
        bm25_retriever: BaseRetriever,
        rrf_k: int = 60,
        fetch_k: int = 20,
    ):
        self.vector_retriever = vector_retriever
        self.bm25_retriever = bm25_retriever
        self.rrf_k = rrf_k  # standard default from the original RRF paper
        self.fetch_k = fetch_k  # candidates pulled from each side before fusing

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        vector_results = self.vector_retriever.retrieve(query, top_k=self.fetch_k)
        bm25_results = self.bm25_retriever.retrieve(query, top_k=self.fetch_k)

        fused_scores: dict[str, float] = {}
        chunk_by_id = {}
        for results in (vector_results, bm25_results):
            for rank, item in enumerate(results, start=1):
                chunk_id = item.chunk.chunk_id
                chunk_by_id[chunk_id] = item.chunk
                fused_scores[chunk_id] = fused_scores.get(chunk_id, 0.0) + 1.0 / (self.rrf_k + rank)

        k = min(top_k, len(fused_scores))
        ranked_ids = sorted(fused_scores, key=lambda cid: fused_scores[cid], reverse=True)[:k]
        return [RetrievedChunk(chunk=chunk_by_id[cid], score=fused_scores[cid]) for cid in ranked_ids]
