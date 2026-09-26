from app.core.logging import get_logger
from app.models.query import RetrievedChunk
from app.retrieval.base import BaseRetriever

logger = get_logger(__name__)

DEFAULT_RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class CrossEncoderReranker:
    def __init__(self, model_name: str = DEFAULT_RERANKER_MODEL):
        from sentence_transformers import CrossEncoder  # lazy import

        logger.info("Loading cross-encoder reranker: %s", model_name)
        self._model = CrossEncoder(model_name)

    def rerank(
        self, query: str, candidates: list[RetrievedChunk], top_k: int = 5
    ) -> list[RetrievedChunk]:
        if not candidates:
            return []
        pairs = [(query, item.chunk.text) for item in candidates]
        scores = self._model.predict(pairs)
        reranked = sorted(zip(candidates, scores), key=lambda pair: pair[1], reverse=True)
        k = min(top_k, len(reranked))
        return [RetrievedChunk(chunk=item.chunk, score=float(s)) for item, s in reranked[:k]]


class NoOpReranker:
    """Fallback: no re-scoring, just truncates the first-stage results."""

    def rerank(
        self, query: str, candidates: list[RetrievedChunk], top_k: int = 5
    ) -> list[RetrievedChunk]:
        return candidates[:top_k]


def get_reranker(model_name: str = DEFAULT_RERANKER_MODEL):
    try:
        return CrossEncoderReranker(model_name)
    except Exception as exc:  # noqa: BLE001 - deliberate broad fallback
        logger.warning(
            "Falling back to NoOpReranker — cross-encoder unavailable (%s). ",
            exc,
        )
        return NoOpReranker()


class RerankingRetriever(BaseRetriever):
    """Wraps any first-stage retriever with a reranking pass."""

    def __init__(self, base_retriever: BaseRetriever, reranker, fetch_k: int = 20):
        self.base_retriever = base_retriever
        self.reranker = reranker
        self.fetch_k = fetch_k

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        candidates = self.base_retriever.retrieve(query, top_k=self.fetch_k)
        return self.reranker.rerank(query, candidates, top_k=top_k)
