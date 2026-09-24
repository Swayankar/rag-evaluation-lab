from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.embeddings.embedder import get_embedder
from app.generation.answer_generator import AnswerGenerator
from app.models.query import QueryResult, RetrievedChunk
from app.pipelines.strategy import StrategyConfig
from app.retrieval.vector_search import VectorStore

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
        self.vector_store = self._load_vector_store()
        # Lazy: don't require a Grok API key just to construct the pipeline
        # (e.g. testing retrieval alone). The key is only checked once an
        # answer is actually generated.
        self._answer_generator = answer_generator

    @property
    def answer_generator(self) -> AnswerGenerator:
        if self._answer_generator is None:
            self._answer_generator = AnswerGenerator()
        return self._answer_generator

    def _load_vector_store(self) -> VectorStore:
        path = self.settings.vector_store_path
        if not (path / "embeddings.npy").exists():
            raise FileNotFoundError(
                f"No vector store found at {path}. Run "
                "scripts/build_vector_store.py first (Phase 2)."
            )
        return VectorStore.load(path)

    def answer(self, question: str) -> QueryResult:
        query_embedding = self.embedder.embed_query(question)
        raw_results = self.vector_store.search(query_embedding, top_k=self.strategy.top_k)
        retrieved = [RetrievedChunk(chunk=chunk, score=score) for chunk, score in raw_results]

        logger.info("Retrieved %d chunks for question: %r", len(retrieved), question)
        return self.answer_generator.generate(question, retrieved, strategy=self.strategy.name)
