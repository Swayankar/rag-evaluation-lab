import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app.core.config import Settings
from app.generation.answer_generator import AnswerGenerator
from app.generation.llm import GroqClient, GroqClientError
from app.generation.prompts import build_user_prompt
from app.models.document import Chunk
from app.models.query import RetrievedChunk
from app.pipelines.rag_pipeline import RAGPipeline
from app.retrieval.vector_search import VectorStore


def _make_retrieved(chunk_id: str, text: str, score: float = 0.9) -> RetrievedChunk:
    chunk = Chunk(
        chunk_id=chunk_id,
        document_id="parental_leave_policy",
        document_name="Parental Leave Policy",
        department="hr",
        page=2,
        chunk_index=0,
        text=text,
    )
    return RetrievedChunk(chunk=chunk, score=score)


class FakeLLMClient:
    """Stands in for GroqClient in tests — returns a canned response
    instead of calling the real API."""

    def __init__(self, canned_response: str):
        self.canned_response = canned_response
        self.last_system_prompt: str | None = None
        self.last_user_prompt: str | None = None

    def chat(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        self.last_system_prompt = system_prompt
        self.last_user_prompt = user_prompt
        return self.canned_response


def test_build_user_prompt_includes_context_and_question():
    retrieved = [_make_retrieved("c1", "Employees get 16 weeks of leave.")]
    prompt = build_user_prompt("How much parental leave?", retrieved)

    assert "16 weeks" in prompt
    assert "How much parental leave?" in prompt
    assert "[1]" in prompt


def test_build_user_prompt_handles_no_results():
    prompt = build_user_prompt("Unanswerable question", [])
    assert "No relevant context" in prompt


def test_answer_generator_extracts_valid_citations():
    retrieved = [
        _make_retrieved("c1", "Employees get 16 weeks of leave."),
        _make_retrieved("c2", "Leave must be taken within 12 months."),
    ]
    fake_llm = FakeLLMClient("Employees get 16 weeks [1], usable within 12 months [2].")
    generator = AnswerGenerator(llm_client=fake_llm)

    result = generator.generate("How much leave?", retrieved)

    assert len(result.citations) == 2
    assert result.citations[0].chunk_id == "c1"
    assert result.citations[1].chunk_id == "c2"
    assert result.latency_ms >= 0


def test_answer_generator_ignores_out_of_range_citations():
    retrieved = [_make_retrieved("c1", "Employees get 16 weeks of leave.")]
    fake_llm = FakeLLMClient("Answer citing a source that doesn't exist [5].")
    generator = AnswerGenerator(llm_client=fake_llm)

    result = generator.generate("How much leave?", retrieved)

    assert result.citations == []


def test_groq_client_requires_api_key():
    settings = Settings(groq_api_key="", _env_file=None)
    with pytest.raises(GroqClientError):
        GroqClient(settings=settings)


def test_rag_pipeline_requires_vector_store():
    with tempfile.TemporaryDirectory() as tmp:
        settings = Settings(
            embedding_backend="hashing",
            vector_store_dir=str(Path(tmp) / "does-not-exist"),
            groq_api_key="fake-key-for-this-test",
            _env_file=None,
        )
        with pytest.raises(FileNotFoundError):
            RAGPipeline(settings=settings)


def test_rag_pipeline_answer_end_to_end_with_fake_llm():
    with tempfile.TemporaryDirectory() as tmp:
        vector_store_dir = Path(tmp) / "vector_store"
        chunk = Chunk(
            chunk_id="c1",
            document_id="doc",
            document_name="Doc",
            department="hr",
            page=1,
            chunk_index=0,
            text="Employees get 16 weeks of parental leave.",
        )

        from app.embeddings.embedder import HashingEmbedder

        embedder = HashingEmbedder()
        store = VectorStore()
        store.build([chunk], embedder.embed_texts([chunk.text]))
        store.save(vector_store_dir)

        settings = Settings(
            embedding_backend="hashing",
            vector_store_dir=str(vector_store_dir),
            groq_api_key="fake-key-for-this-test",
            _env_file=None,
        )
        fake_llm = FakeLLMClient("You get 16 weeks [1].")
        pipeline = RAGPipeline(
            settings=settings, answer_generator=AnswerGenerator(llm_client=fake_llm)
        )

        result = pipeline.answer("How much parental leave?")

        assert "16 weeks" in result.answer
        assert len(result.retrieved_chunks) == 1
        assert result.citations[0].chunk_id == "c1"


if __name__ == "__main__":
    test_build_user_prompt_includes_context_and_question()
    test_build_user_prompt_handles_no_results()
    test_answer_generator_extracts_valid_citations()
    test_answer_generator_ignores_out_of_range_citations()
    test_groq_client_requires_api_key()
    test_rag_pipeline_requires_vector_store()
    test_rag_pipeline_answer_end_to_end_with_fake_llm()
    print("✅ All generation/pipeline tests passed.")