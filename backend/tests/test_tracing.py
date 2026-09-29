import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from langsmith import Client, tracing_context

import app.tracing.langsmith as tracing
from app.core.config import Settings
from app.embeddings.embedder import HashingEmbedder
from app.generation.answer_generator import AnswerGenerator
from app.generation.llm import GroqClient, GroqClientError
from app.models.document import Chunk
from app.models.query import RetrievedChunk
from app.pipelines.rag_pipeline import RAGPipeline
from app.pipelines.strategy import StrategyConfig
from app.retrieval.vector_search import VectorStore

_TRACING_ENV_VARS = [
    "LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2", "LANGSMITH_API_KEY", "LANGCHAIN_API_KEY",
    "LANGSMITH_PROJECT", "LANGCHAIN_PROJECT", "LANGSMITH_ENDPOINT", "LANGCHAIN_ENDPOINT",
]

SECRET = "gsk_SECRET_KEY_123"


class RecordingClient(Client):
    """A LangSmith client that records what would be sent instead of sending it."""

    def __init__(self):
        super().__init__(api_url="http://localhost:9", api_key="test-key", auto_batch_tracing=False)
        self.created: list[dict] = []
        self.updated: list[dict] = []

    def create_run(self, **kwargs):
        self.created.append(kwargs)

    def update_run(self, run_id, **kwargs):
        self.updated.append({"id": run_id, **kwargs})


@pytest.fixture
def clean_tracing_env(monkeypatch):
    """Register every tracing env var with monkeypatch so whatever
    configure_tracing() sets is undone at teardown."""
    for var in _TRACING_ENV_VARS:
        monkeypatch.setenv(var, "")
        monkeypatch.delenv(var)
    return monkeypatch


# --- configure_tracing -------------------------------------------------

def test_configure_tracing_off_by_default_leaves_env_alone(clean_tracing_env):
    settings = Settings(langchain_tracing_v2=False, langchain_api_key="lsv2_x", _env_file=None)

    assert tracing.configure_tracing(settings) is False
    assert "LANGSMITH_TRACING" not in os.environ
    assert "LANGSMITH_API_KEY" not in os.environ


def test_configure_tracing_enabled_without_key_is_disabled(clean_tracing_env):
    settings = Settings(langchain_tracing_v2=True, langchain_api_key="", _env_file=None)

    assert tracing.configure_tracing(settings) is False
    assert "LANGSMITH_TRACING" not in os.environ


def test_configure_tracing_enabled_sets_both_env_var_families(clean_tracing_env):
    settings = Settings(
        langchain_tracing_v2=True,
        langchain_api_key="lsv2_abc",
        langchain_project="my-project",
        langsmith_endpoint="https://eu.api.smith.langchain.com",
        _env_file=None,
    )

    assert tracing.configure_tracing(settings) is True
    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
    assert os.environ["LANGSMITH_API_KEY"] == "lsv2_abc"
    assert os.environ["LANGCHAIN_API_KEY"] == "lsv2_abc"
    assert os.environ["LANGSMITH_PROJECT"] == "my-project"
    assert os.environ["LANGSMITH_ENDPOINT"] == "https://eu.api.smith.langchain.com"


def test_configure_tracing_force_enables_with_just_a_key(clean_tracing_env):
    settings = Settings(langchain_tracing_v2=False, langchain_api_key="lsv2_abc", _env_file=None)

    assert tracing.configure_tracing(settings, force=True) is True
    assert os.environ["LANGSMITH_API_KEY"] == "lsv2_abc"


def test_force_still_requires_a_key(clean_tracing_env):
    settings = Settings(langchain_tracing_v2=False, langchain_api_key="", _env_file=None)
    assert tracing.configure_tracing(settings, force=True) is False


def test_traceable_shim_is_a_noop_when_langsmith_missing(monkeypatch):
    monkeypatch.setattr(tracing, "LANGSMITH_AVAILABLE", False)

    def f(x):
        return x + 1

    assert tracing.traceable(f) is f  # bare @traceable
    assert tracing.traceable(name="x", run_type="chain")(f) is f  # @traceable(...)
    assert tracing.traceable(name="x")(f)(1) == 2


def test_helpers_are_silent_noops_when_not_tracing():
    # Outside any traced call, with tracing off, none of these may raise.
    tracing.annotate_current_run(metadata={"a": 1}, tags=["t"])
    tracing.flush_traces()


# --- pipeline instrumentation -----------------------------------------

def _make_pipeline(tmp: Path, strategy: StrategyConfig, llm_client=None):
    chunks = [
        Chunk(chunk_id="pw_000", document_id="password_policy", document_name="Password Policy",
              department="it", page=1, chunk_index=0, text="Passwords must be at least twelve characters."),
        Chunk(chunk_id="pl_000", document_id="parental_leave_policy", document_name="Parental Leave Policy",
              department="hr", page=1, chunk_index=0, text="Employees get sixteen weeks of leave."),
    ]
    embedder = HashingEmbedder()
    store = VectorStore()
    store.build(chunks, embedder.embed_texts([c.text for c in chunks]))
    store.save(tmp / "vs")
    (tmp / "chunks").mkdir(exist_ok=True)
    (tmp / "chunks" / "fixed_chunks.json").write_text(json.dumps([c.model_dump() for c in chunks]))

    settings = Settings(
        embedding_backend="hashing",
        vector_store_dir=str(tmp / "vs"),
        processed_chunks_dir=str(tmp / "chunks"),
        groq_api_key=SECRET,
        _env_file=None,
    )
    llm_client = llm_client or GroqClient(settings)
    return RAGPipeline(settings=settings, strategy=strategy, answer_generator=AnswerGenerator(llm_client=llm_client))


def _fake_groq_response(text="Twelve characters [1]."):
    resp = mock.Mock()
    resp.raise_for_status = lambda: None
    resp.json = lambda: {"choices": [{"message": {"content": text}}]}
    return resp


def test_pipeline_emits_expected_span_tree():
    client = RecordingClient()
    with tempfile.TemporaryDirectory() as tmp:
        pipeline = _make_pipeline(
            Path(tmp), StrategyConfig(name="fixed_hybrid", retrieval_strategy="hybrid", top_k=2)
        )
        with mock.patch("requests.post", return_value=_fake_groq_response()), \
                tracing_context(enabled=True, client=client):
            pipeline.answer("How long must a password be?")

    by_id = {c["id"]: c for c in client.created}

    def parent_name(c):
        pid = c.get("parent_run_id")
        return by_id[pid]["name"] if pid in by_id else None

    tree = {c["name"]: (c["run_type"], parent_name(c)) for c in client.created}
    assert tree == {
        "rag_pipeline": ("chain", None),
        "hybrid_search": ("retriever", "rag_pipeline"),
        "vector_search": ("retriever", "hybrid_search"),
        "bm25_search": ("retriever", "hybrid_search"),
        "generate_answer": ("chain", "rag_pipeline"),
        "groq_chat": ("llm", "generate_answer"),
    }


def test_traces_never_contain_the_api_key_or_self():
    client = RecordingClient()
    with tempfile.TemporaryDirectory() as tmp:
        pipeline = _make_pipeline(Path(tmp), StrategyConfig(top_k=2))
        with mock.patch("requests.post", return_value=_fake_groq_response()), \
                tracing_context(enabled=True, client=client):
            pipeline.answer("How long must a password be?")

    payload = json.dumps(client.created + client.updated, default=str)
    assert SECRET not in payload
    for span in client.created:
        assert "self" not in (span.get("inputs") or {})


def test_strategy_metadata_and_tags_reach_the_root_span():
    client = RecordingClient()
    with tempfile.TemporaryDirectory() as tmp:
        pipeline = _make_pipeline(
            Path(tmp), StrategyConfig(name="fixed_bm25", retrieval_strategy="bm25", top_k=2)
        )
        with mock.patch("requests.post", return_value=_fake_groq_response()), \
                tracing_context(enabled=True, client=client):
            pipeline.answer("How long must a password be?")

    root_id = next(c["id"] for c in client.created if c["name"] == "rag_pipeline")
    # Metadata added mid-run lands on the final update, not the initial create.
    final = next(u for u in client.updated if u["id"] == root_id)
    meta = final["extra"]["metadata"]
    assert meta["retrieval_strategy"] == "bm25"
    assert meta["chunking_strategy"] == "fixed"
    assert meta["top_k"] == 2
    assert "fixed_bm25" in final["tags"]


def test_llm_span_records_model_name():
    client = RecordingClient()
    with tempfile.TemporaryDirectory() as tmp:
        pipeline = _make_pipeline(Path(tmp), StrategyConfig(top_k=2))
        with mock.patch("requests.post", return_value=_fake_groq_response()), \
                tracing_context(enabled=True, client=client):
            pipeline.answer("How long must a password be?")

    llm_id = next(c["id"] for c in client.created if c["name"] == "groq_chat")
    final = next(u for u in client.updated if u["id"] == llm_id)
    assert final["extra"]["metadata"]["ls_model_name"] == pipeline.settings.groq_model
    assert final["extra"]["metadata"]["ls_provider"] == "groq"


def test_retriever_span_uses_langsmith_document_format():
    client = RecordingClient()
    with tempfile.TemporaryDirectory() as tmp:
        pipeline = _make_pipeline(Path(tmp), StrategyConfig(top_k=2))
        with mock.patch("requests.post", return_value=_fake_groq_response()), \
                tracing_context(enabled=True, client=client):
            pipeline.answer("How long must a password be?")

    vs_id = next(c["id"] for c in client.created if c["name"] == "vector_search")
    outputs = next(u for u in client.updated if u["id"] == vs_id)["outputs"]
    doc = outputs["documents"][0]
    assert doc["type"] == "Document"
    assert "twelve characters" in doc["page_content"] or "sixteen weeks" in doc["page_content"]
    assert {"chunk_id", "document_id", "score"} <= set(doc["metadata"])


def test_nothing_is_recorded_when_tracing_is_disabled():
    client = RecordingClient()
    with tempfile.TemporaryDirectory() as tmp:
        pipeline = _make_pipeline(Path(tmp), StrategyConfig(top_k=2))
        with mock.patch("requests.post", return_value=_fake_groq_response()), \
                tracing_context(enabled=False, client=client):
            result = pipeline.answer("How long must a password be?")

    assert client.created == []
    assert "Twelve characters" in result.answer  # and the pipeline still works normally


# --- latency now covers retrieval -------------------------------------

def test_latency_includes_retrieval_time():
    class FastLLM:
        def chat(self, system_prompt, user_prompt, **kwargs):
            return "answer [1]"

    with tempfile.TemporaryDirectory() as tmp:
        pipeline = _make_pipeline(Path(tmp), StrategyConfig(top_k=2), llm_client=FastLLM())

        real_retrieve = pipeline.retriever.retrieve

        def slow_retrieve(query, top_k=5):
            time.sleep(0.15)
            return real_retrieve(query, top_k=top_k)

        pipeline.retriever.retrieve = slow_retrieve
        result = pipeline.answer("How long must a password be?")

    assert result.latency_ms >= 150


# --- GroqClient malformed-response fix --------------------------------

def test_groq_client_reports_non_json_body_instead_of_unbound_error():
    settings = Settings(groq_api_key=SECRET, _env_file=None)
    bad = mock.Mock()
    bad.raise_for_status = lambda: None
    bad.text = "<html>502 Bad Gateway</html>"
    bad.json = mock.Mock(side_effect=ValueError("Expecting value"))

    with mock.patch("requests.post", return_value=bad):
        with pytest.raises(GroqClientError) as excinfo:
            GroqClient(settings).chat("sys", "user")
            
    assert "502 Bad Gateway" in str(excinfo.value)


def test_retrieved_to_documents_shape():
    chunk = Chunk(chunk_id="c1", document_id="d1", document_name="D1", department="hr",
                  page=3, chunk_index=0, text="hello")
    out = tracing.retrieved_to_documents([RetrievedChunk(chunk=chunk, score=0.5)])
    assert out["documents"][0]["page_content"] == "hello"
    assert out["documents"][0]["metadata"]["page"] == 3


# --- failed calls: process_outputs receives None ------------------------

def test_output_processors_tolerate_none():
    from app.generation.llm import _llm_trace_outputs

    assert tracing.summarize_query_result(None) == {}
    assert tracing.retrieved_to_documents(None) == {"documents": []}
    assert tracing.retrieved_to_documents([]) == {"documents": []}
    assert _llm_trace_outputs(None) == {}  # not {"...content": "None"}


@pytest.mark.parametrize("tracing_on", [True, False])
def test_a_failing_llm_call_logs_no_tracing_warnings(caplog, tracing_on):
    class ExplodingLLM:
        def chat(self, system_prompt, user_prompt, **kwargs):
            raise GroqClientError("Groq is down")

    client = RecordingClient()
    with tempfile.TemporaryDirectory() as tmp:
        pipeline = _make_pipeline(Path(tmp), StrategyConfig(top_k=2), llm_client=ExplodingLLM())
        with caplog.at_level("WARNING"), tracing_context(enabled=tracing_on, client=client):
            with pytest.raises(GroqClientError):
                pipeline.answer("How long must a password be?")

    # Previously: 'process_outputs failed ... dropping outputs' on every failed answer,
    # even with tracing off.
    assert not [r for r in caplog.records if "process_outputs failed" in r.getMessage()]


def test_failed_llm_span_is_not_recorded_with_a_fake_none_answer():
    settings = Settings(groq_api_key=SECRET, _env_file=None)
    bad = mock.Mock()
    bad.raise_for_status = mock.Mock(side_effect=__import__("requests").HTTPError("500"))
    bad.text = "boom"

    client = RecordingClient()
    with mock.patch("requests.post", return_value=bad), tracing_context(enabled=True, client=client):
        with pytest.raises(GroqClientError):
            GroqClient(settings).chat("sys", "user")

    llm_id = next(c["id"] for c in client.created if c["name"] == "groq_chat")
    final = next(u for u in client.updated if u["id"] == llm_id)
    assert "None" not in json.dumps(final.get("outputs") or {})
    assert final.get("error")  # the failure itself is still recorded, properly