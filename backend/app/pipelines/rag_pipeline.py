"""
The end-to-end pipeline: retrieve the top-K chunks for the question
(via whichever retrieval strategy StrategyConfig selects), then
generate an answer with Groq.
"""
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.embeddings.embedder import get_embedder
from app.generation.answer_generator import AnswerGenerator
from app.models.query import QueryResult
from app.pipelines.strategy import StrategyConfig
from app.retrieval.base import BaseRetriever
from app.retrieval.bm25_search import BM25Retriever
from app.retrieval.hybrid_search import HybridRetriever
from app.retrieval.reranker import RerankingRetriever, get_reranker
from app.retrieval.vector_search import VectorRetriever, VectorStore

logger = get_logger(__name__)


class RAGPipeline:
    def __init__(
        self,
        settings: Settings | None = None,
        strategy: StrategyConfig | None = None,
        answer_generator: AnswerGenerator | None = None,
    ):
        self.settings = settings or get_settings()
        self.strategy = strategy or StrategyConfig()
        self.embedder = get_embedder(self.settings)
        self.retriever = self._build_retriever()
        # Lazy: don't require a Groq API key just to construct the pipeline
        # (e.g. testing retrieval alone). The key is only checked once an
        # answer is actually generated.
        self._answer_generator = answer_generator

    @property
    def answer_generator(self) -> AnswerGenerator:
        if self._answer_generator is None:
            self._answer_generator = AnswerGenerator()
        return self._answer_generator

    def _build_retriever(self) -> BaseRetriever:
        strategy_name = self.strategy.retrieval_strategy

        if strategy_name == "vector":
            return VectorRetriever(self._load_vector_store(), self.embedder)

        if strategy_name == "bm25":
            return self._load_bm25_retriever()

        # hybrid and hybrid_rerank both need both retrievers
        vector_retriever = VectorRetriever(self._load_vector_store(), self.embedder)
        bm25_retriever = self._load_bm25_retriever()
        hybrid = HybridRetriever(vector_retriever, bm25_retriever)

        if strategy_name == "hybrid":
            return hybrid

        # hybrid_rerank: rerank the hybrid candidates with a cross-encoder
        return RerankingRetriever(hybrid, get_reranker())

    def _load_vector_store(self) -> VectorStore:
        path = self.settings.vector_store_path
        if not (path / "embeddings.npy").exists():
            raise FileNotFoundError(
                f"No vector store found at {path}. Run "
                "scripts/build_vector_store.py first (Phase 2)."
            )
        return VectorStore.load(path)

    def _load_bm25_retriever(self) -> BM25Retriever:
        chunks_path = self.settings.processed_chunks_path / "fixed_chunks.json"
        if not chunks_path.exists():
            raise FileNotFoundError(
                f"No chunks found at {chunks_path}. Run "
                "scripts/ingest_documents.py first (Phase 1)."
            )
        return BM25Retriever.from_chunks_file(chunks_path)

    def answer(self, question: str) -> QueryResult:
        retrieved = self.retriever.retrieve(question, top_k=self.strategy.top_k)
        logger.info(
            "Retrieved %d chunks (strategy=%s) for question: %r",
            len(retrieved),
            self.strategy.retrieval_strategy,
            question,
        )
        return self.answer_generator.generate(question, retrieved, strategy=self.strategy.name)