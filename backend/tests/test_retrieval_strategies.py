import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.embeddings.embedder import HashingEmbedder
from app.models.document import Chunk
from app.models.query import RetrievedChunk
from app.retrieval.bm25_search import BM25Retriever
from app.retrieval.hybrid_search import HybridRetriever
from app.retrieval.reranker import NoOpReranker, RerankingRetriever
from app.retrieval.vector_search import VectorRetriever, VectorStore


def _make_chunk(chunk_id: str, text: str) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id="doc",
        document_name="Doc",
        department="hr",
        page=1,
        chunk_index=0,
        text=text,
    )


CHUNKS = [
    _make_chunk("leave", "Employees get sixteen weeks of paid parental leave."),
    _make_chunk("password", "Passwords must be at least twelve characters long."),
    _make_chunk("expense", "Meal expenses over fifty dollars require a receipt."),
]


class FakeVectorRetriever:
    """A retriever that returns a fixed rank order, for testing fusion
    logic in isolation from real embeddings."""

    def __init__(self, ranked_chunks: list[Chunk]):
        self.ranked_chunks = ranked_chunks

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        return [
            RetrievedChunk(chunk=c, score=1.0 - i * 0.1)
            for i, c in enumerate(self.ranked_chunks[:top_k])
        ]


def test_bm25_retriever_ranks_exact_keyword_match_top():
    retriever = BM25Retriever(CHUNKS)
    results = retriever.retrieve("twelve characters password requirement", top_k=3)

    assert results[0].chunk.chunk_id == "password"


def test_bm25_retriever_empty_corpus_returns_nothing():
    retriever = BM25Retriever([])
    assert retriever.retrieve("anything") == []


def test_hybrid_retriever_fuses_both_rankings_via_rrf():
    # vector ranks "leave" first; bm25 ranks "password" first (different
    # orders) — hybrid should blend, with "expense" (bottom of both)
    # ranking last.
    vector = FakeVectorRetriever([CHUNKS[0], CHUNKS[1], CHUNKS[2]])
    bm25 = FakeVectorRetriever([CHUNKS[1], CHUNKS[0], CHUNKS[2]])

    hybrid = HybridRetriever(vector, bm25, fetch_k=3)
    results = hybrid.retrieve("anything", top_k=3)

    result_ids = [r.chunk.chunk_id for r in results]
    assert result_ids[-1] == "expense"
    assert set(result_ids) == {"leave", "password", "expense"}


def test_noop_reranker_just_truncates():
    candidates = [RetrievedChunk(chunk=c, score=1.0) for c in CHUNKS]
    reranker = NoOpReranker()

    result = reranker.rerank("query", candidates, top_k=2)

    assert len(result) == 2
    assert result[0].chunk.chunk_id == "leave"


def test_reranking_retriever_wraps_base_retriever():
    base = FakeVectorRetriever(CHUNKS)
    reranking = RerankingRetriever(base, NoOpReranker(), fetch_k=3)

    results = reranking.retrieve("query", top_k=2)

    assert len(results) == 2


def test_vector_retriever_embeds_query_and_searches_store():
    embedder = HashingEmbedder()
    store = VectorStore()
    store.build(CHUNKS, embedder.embed_texts([c.text for c in CHUNKS]))
    retriever = VectorRetriever(store, embedder)

    results = retriever.retrieve("parental leave duration", top_k=1)

    assert results[0].chunk.chunk_id == "leave"


def test_bm25_retriever_from_chunks_file_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        import json

        chunks_path = Path(tmp) / "fixed_chunks.json"
        chunks_path.write_text(json.dumps([c.model_dump() for c in CHUNKS]))

        retriever = BM25Retriever.from_chunks_file(chunks_path)
        assert len(retriever) == 3


def test_rag_pipeline_with_bm25_and_hybrid_strategies():
    """End-to-end: build a real vector store + chunks file, then run the
    pipeline with each non-default retrieval strategy and confirm it
    retrieves the topically right chunk for a keyword-heavy question."""
    from app.core.config import Settings
    from app.generation.answer_generator import AnswerGenerator
    from app.pipelines.rag_pipeline import RAGPipeline
    from app.pipelines.strategy import StrategyConfig

    class FakeLLMClient:
        def chat(self, system_prompt, user_prompt, **kwargs):
            return "Passwords need twelve characters [1]."

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        chunks_dir = tmp_path / "chunks"
        chunks_dir.mkdir()

        embedder = HashingEmbedder()
        store = VectorStore()
        store.build(CHUNKS, embedder.embed_texts([c.text for c in CHUNKS]))
        store.save(tmp_path / "vector_store")

        import json

        (chunks_dir / "fixed_chunks.json").write_text(
            json.dumps([c.model_dump() for c in CHUNKS])
        )

        for strategy_name in ["bm25", "hybrid", "hybrid_rerank"]:
            settings = Settings(
                embedding_backend="hashing",
                vector_store_dir=str(tmp_path / "vector_store"),
                processed_chunks_dir=str(chunks_dir),
                groq_api_key="fake-key",
                _env_file=None,
            )
            pipeline = RAGPipeline(
                settings=settings,
                strategy=StrategyConfig(retrieval_strategy=strategy_name, top_k=2),
                answer_generator=AnswerGenerator(llm_client=FakeLLMClient()),
            )
            result = pipeline.answer("What are the password character requirements?")
            retrieved_ids = {r.chunk.chunk_id for r in result.retrieved_chunks}
            assert "password" in retrieved_ids, f"strategy={strategy_name} missed the password chunk"


if __name__ == "__main__":
    test_bm25_retriever_ranks_exact_keyword_match_top()
    test_bm25_retriever_empty_corpus_returns_nothing()
    test_hybrid_retriever_fuses_both_rankings_via_rrf()
    test_noop_reranker_just_truncates()
    test_reranking_retriever_wraps_base_retriever()
    test_vector_retriever_embeds_query_and_searches_store()
    test_bm25_retriever_from_chunks_file_roundtrip()
    test_rag_pipeline_with_bm25_and_hybrid_strategies()
    print("✅ All retrieval-strategy tests passed.")