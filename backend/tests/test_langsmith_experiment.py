import json
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from langsmith.schemas import Example

import app.evaluation.langsmith_experiment as lsx
from app.core.config import Settings
from app.embeddings.embedder import HashingEmbedder
from app.evaluation.dataset import EvalDataset, EvalQuestion
from app.evaluation.evaluators.answer import AnswerEvaluator
from app.evaluation.evaluators.grounding import GroundingEvaluator
from app.generation.answer_generator import AnswerGenerator
from app.models.document import Chunk
from app.pipelines.rag_pipeline import RAGPipeline
from app.pipelines.strategy import StrategyConfig
from app.retrieval.vector_search import VectorStore


def _dataset(*questions: EvalQuestion) -> EvalDataset:
    return EvalDataset(questions=list(questions))


Q_PASSWORD = EvalQuestion(
    id="q1",
    question="How long must a password be?",
    relevant_document_ids=["password_policy"],
    expected_answer="At least twelve characters.",
    category="IT",
)
Q_LEAVE = EvalQuestion(
    id="q2",
    question="How many weeks of parental leave?",
    relevant_document_ids=["parental_leave_policy"],
    expected_answer="Sixteen weeks.",
    category="HR",
)


class FakeLangSmithClient:
    def __init__(self, existing: bool = False, fail_examples: bool = False):
        self.existing = existing
        self.fail_examples = fail_examples
        self.created_datasets: list[dict] = []
        self.created_examples: list[dict] = []
        self.deleted: list = []

    def has_dataset(self, dataset_name):
        return self.existing

    def create_dataset(self, dataset_name, description=None):
        self.created_datasets.append({"name": dataset_name, "description": description})
        return type("DS", (), {"id": "dataset-123"})()

    def create_examples(self, dataset_id, examples):
        if self.fail_examples:
            raise RuntimeError("upload blew up")
        self.created_examples.append({"dataset_id": dataset_id, "examples": examples})

    def delete_dataset(self, dataset_id):
        self.deleted.append(dataset_id)


# --- dataset versioning ------------------------------------------------

def test_dataset_name_is_stable_for_identical_content():
    assert lsx.dataset_name_for(_dataset(Q_PASSWORD, Q_LEAVE)) == lsx.dataset_name_for(_dataset(Q_PASSWORD, Q_LEAVE))


def test_dataset_name_changes_when_a_question_changes():
    original = lsx.dataset_name_for(_dataset(Q_PASSWORD))
    edited = lsx.dataset_name_for(
        _dataset(Q_PASSWORD.model_copy(update={"expected_answer": "Eight characters."}))
    )
    assert original != edited
    assert original.startswith("rag-evaluation-lab-")


def test_dataset_name_changes_when_a_question_is_added():
    assert lsx.dataset_name_for(_dataset(Q_PASSWORD)) != lsx.dataset_name_for(_dataset(Q_PASSWORD, Q_LEAVE))


# --- ensure_dataset ----------------------------------------------------

def test_ensure_dataset_creates_and_uploads_examples():
    client = FakeLangSmithClient()
    created = lsx.ensure_dataset(client, _dataset(Q_PASSWORD, Q_LEAVE), "ds-name")

    assert created is True
    assert client.created_datasets[0]["name"] == "ds-name"
    uploaded = client.created_examples[0]
    assert uploaded["dataset_id"] == "dataset-123"
    first = uploaded["examples"][0]
    assert first["inputs"] == {"question": Q_PASSWORD.question}
    assert first["outputs"]["relevant_document_ids"] == ["password_policy"]
    assert first["outputs"]["expected_answer"] == "At least twelve characters."
    assert first["metadata"]["question_id"] == "q1"
    assert first["metadata"]["category"] == "IT"


def test_ensure_dataset_reuses_existing():
    client = FakeLangSmithClient(existing=True)
    assert lsx.ensure_dataset(client, _dataset(Q_PASSWORD), "ds-name") is False
    assert client.created_datasets == []


def test_ensure_dataset_rolls_back_a_half_built_dataset():
    client = FakeLangSmithClient(fail_examples=True)

    with pytest.raises(RuntimeError, match="upload blew up"):
        lsx.ensure_dataset(client, _dataset(Q_PASSWORD), "ds-name")

    assert client.deleted == ["dataset-123"]


# --- evaluator adapters ------------------------------------------------

def _answer_outputs(answer="Twelve characters [1].", doc_id="password_policy", cite=True) -> dict:
    return {
        "question": "q",
        "answer": answer,
        "citations": [{"marker": "[1]", "document_name": "D", "page": 1, "chunk_id": "c1"}] if cite else [],
        "retrieved_chunks": [
            {
                "chunk": {
                    "chunk_id": "c1", "document_id": doc_id, "document_name": "D", "department": "it",
                    "page": 1, "chunk_index": 0, "text": "Passwords must be twelve characters.",
                },
                "score": 0.9,
            }
        ],
        "strategy": "fixed_vector",
        "latency_ms": 12.0,
    }


class CountingJudge:
    def __init__(self, response: str):
        self.response = response
        self.calls = 0

    def chat(self, system_prompt, user_prompt, **kwargs):
        self.calls += 1
        return self.response


def _evaluators_by_name(judge=None, run_llm_judges=True):
    judge = judge or CountingJudge(
        '{"correctness": 5, "relevance": 4, "completeness": 3, "faithfulness": 5, '
        '"likely_hallucination": false, "rationale": "fine"}'
    )
    evs = lsx.build_evaluators(
        top_k=3,
        run_llm_judges=run_llm_judges,
        answer_evaluator=AnswerEvaluator(llm_client=judge),
        grounding_evaluator=GroundingEvaluator(llm_client=judge),
    )
    return {e.__name__: e for e in evs}, judge


def _scores(result: dict) -> dict:
    return {r["key"]: r["score"] for r in result["results"]}


def test_all_five_adapters_are_built_with_judges():
    evs, _ = _evaluators_by_name()
    assert set(evs) == {"retrieval_metrics", "citation_metrics", "system_metrics", "answer_quality", "grounding"}


def test_judges_are_omitted_when_disabled():
    evs, _ = _evaluators_by_name(run_llm_judges=False)
    assert set(evs) == {"retrieval_metrics", "citation_metrics", "system_metrics"}


def test_retrieval_and_citation_adapters_score_correctly():
    evs, _ = _evaluators_by_name()
    inputs = {"question": Q_PASSWORD.question}
    ref = {"relevant_document_ids": ["password_policy"], "expected_answer": "x"}

    retrieval = _scores(evs["retrieval_metrics"](inputs, _answer_outputs(), ref))
    assert retrieval == {"recall_at_k": 1.0, "precision_at_k": 1.0, "mrr": 1.0}

    citation = _scores(evs["citation_metrics"](inputs, _answer_outputs(), ref))
    assert citation == {"num_citations": 1.0, "citation_accuracy": 1.0}


def test_citation_accuracy_is_omitted_not_zero_when_nothing_was_cited():
    evs, _ = _evaluators_by_name()
    out = evs["citation_metrics"](
        {"question": "q"}, _answer_outputs(cite=False), {"relevant_document_ids": ["password_policy"]}
    )
    assert _scores(out) == {"num_citations": 0.0}  # undefined accuracy must not be reported as 0


def test_wrong_document_scores_zero_on_retrieval():
    evs, _ = _evaluators_by_name()
    out = evs["retrieval_metrics"](
        {"question": "q"}, _answer_outputs(doc_id="expense_policy"), {"relevant_document_ids": ["password_policy"]}
    )
    assert _scores(out)["recall_at_k"] == 0.0
    assert _scores(out)["mrr"] == 0.0


def test_judge_adapters_parse_scores_and_flag_hallucination():
    judge = CountingJudge('{"correctness": 5, "relevance": 4, "completeness": 3, "faithfulness": 2, '
                          '"likely_hallucination": true, "rationale": "invented"}')
    evs, _ = _evaluators_by_name(judge=judge)
    inputs = {"question": Q_PASSWORD.question}
    ref = {"relevant_document_ids": ["password_policy"], "expected_answer": "At least twelve."}

    answer = _scores(evs["answer_quality"](inputs, _answer_outputs(), ref))
    assert answer == {"correctness": 5.0, "relevance": 4.0, "completeness": 3.0}

    grounding = _scores(evs["grounding"](inputs, _answer_outputs(), ref))
    assert grounding == {"faithfulness": 2.0, "hallucination": 1.0}


def test_answer_judge_is_skipped_without_a_reference_answer():
    evs, judge = _evaluators_by_name()
    out = evs["answer_quality"](
        {"question": "q"}, _answer_outputs(), {"relevant_document_ids": ["d"], "expected_answer": None}
    )
    assert out == {"results": []}
    assert judge.calls == 0


def test_failed_target_runs_are_skipped_and_cost_no_judge_calls():
    """LangSmith still runs every evaluator when the target raised, handing
    them {'output': None}. That must produce nothing — and not burn Groq calls."""
    evs, judge = _evaluators_by_name()
    failed = {"output": None}
    inputs = {"question": "q"}
    ref = {"relevant_document_ids": ["d"], "expected_answer": "a"}

    for name, ev in evs.items():
        assert ev(inputs, failed, ref) == {"results": []}, name
    assert judge.calls == 0


def test_judges_are_skipped_if_they_cannot_be_constructed(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("GROQ_API_KEY is not configured.")

    monkeypatch.setattr(lsx, "AnswerEvaluator", boom)
    evs = lsx.build_evaluators(top_k=3, run_llm_judges=True)
    assert {e.__name__ for e in evs} == {"retrieval_metrics", "citation_metrics", "system_metrics"}


# --- setup errors ------------------------------------------------------

def test_missing_api_key_gives_a_clear_setup_error():
    settings = Settings(langchain_api_key="", _env_file=None)
    with pytest.raises(lsx.LangSmithSetupError, match="LANGCHAIN_API_KEY"):
        lsx.run_langsmith_experiment(
            pipeline=None, dataset=_dataset(Q_PASSWORD), settings=settings, upload_results=True
        )


def test_unreachable_langsmith_becomes_an_actionable_setup_error(monkeypatch):
    for var in ("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2", "LANGSMITH_API_KEY", "LANGCHAIN_API_KEY",
                "LANGSMITH_PROJECT", "LANGCHAIN_PROJECT"):
        monkeypatch.setenv(var, "")
        monkeypatch.delenv(var)

    class Unreachable(FakeLangSmithClient):
        def has_dataset(self, dataset_name):
            raise ConnectionError("403 Forbidden")

    settings = Settings(langchain_api_key="lsv2_x", _env_file=None)
    with pytest.raises(lsx.LangSmithSetupError) as excinfo:
        lsx.run_langsmith_experiment(
            pipeline=None, dataset=_dataset(Q_PASSWORD), settings=settings,
            client=Unreachable(), upload_results=True,
        )
    message = str(excinfo.value)
    assert "ConnectionError" in message
    assert "LANGSMITH_ENDPOINT" in message


# --- full evaluate() flow, offline -------------------------------------

class ScriptedLLM:
    """Stands in for Groq as the *answer generator*."""

    def __init__(self, fail_on: str | None = None):
        self.fail_on = fail_on

    def chat(self, system_prompt, user_prompt, **kwargs):
        if self.fail_on and self.fail_on in user_prompt:
            raise RuntimeError("simulated Groq outage")
        if "password" in user_prompt.lower():
            return "Passwords must be at least twelve characters [1]."
        return "Sixteen weeks of leave [1]."


def _pipeline(tmp: Path, generator_llm) -> RAGPipeline:
    chunks = [
        Chunk(chunk_id="pw_000", document_id="password_policy", document_name="Password Policy",
              department="it", page=1, chunk_index=0,
              text="Passwords must be at least twelve characters long and include a symbol."),
        Chunk(chunk_id="pl_000", document_id="parental_leave_policy", document_name="Parental Leave Policy",
              department="hr", page=1, chunk_index=0,
              text="Eligible employees may take up to sixteen weeks of paid parental leave."),
    ]
    emb = HashingEmbedder()
    store = VectorStore()
    store.build(chunks, emb.embed_texts([c.text for c in chunks]))
    store.save(tmp / "vs")
    settings = Settings(embedding_backend="hashing", vector_store_dir=str(tmp / "vs"),
                        groq_api_key="fake", _env_file=None)
    return RAGPipeline(
        settings=settings,
        strategy=StrategyConfig(name="fixed_vector", top_k=2),
        answer_generator=AnswerGenerator(llm_client=generator_llm),
    )


def _examples(dataset: EvalDataset) -> list[Example]:
    return [
        Example(
            id=uuid.uuid4(), dataset_id=uuid.uuid4(), created_at="2026-01-01T00:00:00Z",
            inputs={"question": q.question},
            outputs={"expected_answer": q.expected_answer, "relevant_document_ids": q.relevant_document_ids},
        )
        for q in dataset.questions
    ]


def _run_offline(pipeline, dataset, judge=None):
    evs, judge = _evaluators_by_name(judge=judge)
    summary = lsx.run_langsmith_experiment(
        pipeline,
        dataset,
        pipeline.settings,
        upload_results=False,
        data=_examples(dataset),
        evaluators=list(evs.values()),
    )
    return summary, judge


def test_full_experiment_runs_offline_and_averages_every_metric():
    dataset = _dataset(Q_PASSWORD, Q_LEAVE)
    with tempfile.TemporaryDirectory() as tmp:
        summary, judge = _run_offline(_pipeline(Path(tmp), ScriptedLLM()), dataset)

    assert summary.num_examples == 2
    assert summary.num_target_errors == 0
    assert summary.averages["recall_at_k"] == 1.0
    assert summary.averages["mrr"] == 1.0
    assert summary.averages["citation_accuracy"] == 1.0
    assert summary.averages["correctness"] == 5.0
    assert summary.averages["faithfulness"] == 5.0
    assert summary.averages["hallucination"] == 0.0
    assert summary.averages["latency_ms"] >= 0
    assert judge.calls == 4  # 2 questions x (answer judge + grounding judge)


def test_one_failing_question_does_not_sink_the_experiment():
    dataset = _dataset(Q_PASSWORD, Q_LEAVE)
    with tempfile.TemporaryDirectory() as tmp:
        pipeline = _pipeline(Path(tmp), ScriptedLLM(fail_on="password"))
        summary, judge = _run_offline(pipeline, dataset)

    assert summary.num_examples == 2
    assert summary.num_target_errors == 1
    assert summary.averages["recall_at_k"] == 1.0
    assert judge.calls == 2


def test_experiment_metadata_records_the_embedder_actually_used():
    with tempfile.TemporaryDirectory() as tmp:
        pipeline = _pipeline(Path(tmp), ScriptedLLM())
        meta = lsx.experiment_metadata(pipeline, run_llm_judges=True)

    assert meta["embedder"] == "HashingEmbedder"
    assert meta["retrieval_strategy"] == "vector"
    assert meta["chunking_strategy"] == "fixed"
    assert meta["llm_judges"] is True
    assert "reranker" not in meta


def test_experiment_metadata_records_a_noop_reranker_fallback():
    from app.retrieval.reranker import NoOpReranker, RerankingRetriever

    with tempfile.TemporaryDirectory() as tmp:
        pipeline = _pipeline(Path(tmp), ScriptedLLM())
        pipeline.retriever = RerankingRetriever(pipeline.retriever, NoOpReranker())
        meta = lsx.experiment_metadata(pipeline, run_llm_judges=False)

    assert meta["reranker"] == "NoOpReranker"


def test_summarize_results_ignores_none_scores():
    class R:
        def __init__(self, key, score):
            self.key, self.score = key, score

    class Run:
        error = None

    items = [{"run": Run(), "evaluation_results": {"results": [R("m", 1.0), R("n", None)]}},
             {"run": Run(), "evaluation_results": {"results": [R("m", 0.0)]}}]
    num, errs, avgs = lsx.summarize_results(items)
    assert (num, errs) == (2, 0)
    assert avgs == {"m": 0.5}

if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))