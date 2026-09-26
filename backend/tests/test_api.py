import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.dependencies import get_rag_pipeline
from app.embeddings.embedder import HashingEmbedder
from app.generation.answer_generator import AnswerGenerator
from app.main import app
from app.models.document import Chunk
from app.pipelines.rag_pipeline import RAGPipeline
from app.retrieval.vector_search import VectorStore


class FakeLLMClient:
    def chat(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        return "You get 16 weeks of parental leave [1]."


def _build_fake_pipeline(tmp_path: Path) -> RAGPipeline:
    chunk = Chunk(
        chunk_id="parental_leave_policy_000",
        document_id="parental_leave_policy",
        document_name="Parental Leave Policy",
        department="hr",
        year=None,
        page=1,
        chunk_index=0,
        text="Employees get 16 weeks of paid parental leave.",
    )
    embedder = HashingEmbedder()
    store = VectorStore()
    store.build([chunk], embedder.embed_texts([chunk.text]))
    vector_store_dir = tmp_path / "vector_store"
    store.save(vector_store_dir)

    settings = Settings(
        embedding_backend="hashing",
        vector_store_dir=str(vector_store_dir),
        groq_api_key="fake-key-for-tests",
        _env_file=None,
    )
    return RAGPipeline(settings=settings, answer_generator=AnswerGenerator(llm_client=FakeLLMClient()))


def _write_fake_chunks(tmp_path: Path) -> Settings:
    chunks_dir = tmp_path / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    chunks = [
        {
            "chunk_id": "parental_leave_policy_000",
            "document_id": "parental_leave_policy",
            "document_name": "Parental Leave Policy",
            "department": "hr",
            "year": None,
            "page": 1,
            "chunk_index": 0,
            "chunking_strategy": "fixed",
            "text": "Employees get 16 weeks of paid parental leave.",
        },
        {
            "chunk_id": "password_policy_000",
            "document_id": "password_policy",
            "document_name": "Password Policy",
            "department": "it",
            "year": None,
            "page": 1,
            "chunk_index": 0,
            "chunking_strategy": "fixed",
            "text": "Passwords must be at least twelve characters.",
        },
    ]
    (chunks_dir / "fixed_chunks.json").write_text(json.dumps(chunks))
    return Settings(processed_chunks_dir=str(chunks_dir), _env_file=None)


def test_health_check():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_query_without_pipeline_returns_503():
    # raises FileNotFoundError -> get_rag_pipeline turns that into a 503.
    from fastapi import HTTPException

    def _pipeline_not_ready():
        raise HTTPException(status_code=503, detail="No vector store found yet.")

    app.dependency_overrides[get_rag_pipeline] = _pipeline_not_ready
    try:
        client = TestClient(app)
        response = client.post("/query", json={"question": "anything"})
        assert response.status_code == 503
    finally:
        app.dependency_overrides.clear()


def test_query_returns_answer_with_citations(tmp_path):
    pipeline = _build_fake_pipeline(tmp_path)
    app.dependency_overrides[get_rag_pipeline] = lambda: pipeline
    try:
        client = TestClient(app)
        response = client.post(
            "/query", json={"question": "How many weeks of parental leave?"}
        )
        assert response.status_code == 200
        body = response.json()
        assert "16 weeks" in body["answer"]
        assert len(body["citations"]) == 1
        assert body["citations"][0]["document_name"] == "Parental Leave Policy"
        assert len(body["retrieved_chunks"]) == 1
    finally:
        app.dependency_overrides.clear()


def test_query_rejects_empty_question(tmp_path):
    # Override the pipeline dependency so only the request validation is
    # under test here — without this, the missing-pipeline 503 would win.
    pipeline = _build_fake_pipeline(tmp_path)
    app.dependency_overrides[get_rag_pipeline] = lambda: pipeline
    try:
        client = TestClient(app)
        response = client.post("/query", json={"question": ""})
        assert response.status_code == 422  # pydantic min_length validation
    finally:
        app.dependency_overrides.clear()


def test_documents_endpoint_lists_ingested_docs(tmp_path):
    fake_settings = _write_fake_chunks(tmp_path)
    app.dependency_overrides[get_settings] = lambda: fake_settings
    try:
        client = TestClient(app)
        response = client.get("/documents")
        assert response.status_code == 200
        body = response.json()
        assert body["total_chunks"] == 2
        doc_ids = {d["document_id"] for d in body["documents"]}
        assert doc_ids == {"parental_leave_policy", "password_policy"}
    finally:
        app.dependency_overrides.clear()


def test_documents_endpoint_503_when_not_ingested(tmp_path):
    empty_settings = Settings(processed_chunks_dir=str(tmp_path / "nope"), _env_file=None)
    app.dependency_overrides[get_settings] = lambda: empty_settings
    try:
        client = TestClient(app)
        response = client.get("/documents")
        assert response.status_code == 503
    finally:
        app.dependency_overrides.clear()


def test_query_with_explicit_retrieval_strategy_bypasses_default_pipeline(tmp_path, monkeypatch):
    """A request with retrieval_strategy != "vector" should route through
    get_pipeline_for_strategy instead of the default cached pipeline."""
    import app.api.query as query_module

    default_pipeline = _build_fake_pipeline(tmp_path)
    strategy_pipeline = _build_fake_pipeline(tmp_path)

    app.dependency_overrides[get_rag_pipeline] = lambda: default_pipeline
    monkeypatch.setattr(
        query_module, "get_pipeline_for_strategy", lambda strategy: strategy_pipeline
    )
    try:
        client = TestClient(app)
        response = client.post(
            "/query",
            json={"question": "How much leave?", "retrieval_strategy": "hybrid"},
        )
        assert response.status_code == 200
        assert "16 weeks" in response.json()["answer"]
    finally:
        app.dependency_overrides.clear()


if __name__ == "__main__":
    import tempfile

    test_health_check()
    test_query_without_pipeline_returns_503()
    with tempfile.TemporaryDirectory() as tmp:
        test_query_returns_answer_with_citations(Path(tmp))
    with tempfile.TemporaryDirectory() as tmp:
        test_query_rejects_empty_question(Path(tmp))
    with tempfile.TemporaryDirectory() as tmp:
        test_documents_endpoint_lists_ingested_docs(Path(tmp))
    with tempfile.TemporaryDirectory() as tmp:
        test_documents_endpoint_503_when_not_ingested(Path(tmp))
    print("✅ All API tests passed. (run test_query_with_explicit_retrieval_strategy via pytest for monkeypatch)")