import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pytest

from app.core.config import Settings
from app.embeddings.embedder import HashingEmbedder
from app.evaluation.dataset import EvalDataset, EvalQuestion
from app.evaluation.evaluators.answer import AnswerEvaluator
from app.evaluation.evaluators.grounding import GroundingEvaluator
from app.evaluation.runner import EvaluationRunner
from app.generation.answer_generator import AnswerGenerator
from app.models.document import Chunk
from app.models.query import Citation, QueryResult, RetrievedChunk
from app.pipelines.rag_pipeline import RAGPipeline
from app.pipelines.strategy import StrategyConfig
from app.retrieval.vector_search import VectorStore


def _make_retrieved(document_id: str, chunk_id: str, text: str) -> RetrievedChunk:
    chunk = Chunk(
        chunk_id=chunk_id,
        document_id=document_id,
        document_name=document_id.title(),
        department="hr",
        page=1,
        chunk_index=0,
        text=text,
    )
    return RetrievedChunk(chunk=chunk, score=0.9)


class FakeJudgeClient:
    """Stands in for GroqClient — returns a canned JSON-ish response
    instead of calling the real API."""

    def __init__(self, response: str):
        self.response = response
        self.calls = 0

    def chat(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        self.calls += 1
        return self.response


class FailingJudgeClient:
    def chat(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        raise RuntimeError("simulated Groq failure")


def _make_result(answer="16 weeks [1].") -> QueryResult:
    retrieved = [_make_retrieved("parental_leave_policy", "c1", "Employees get sixteen weeks of leave.")]
    citations = [Citation(marker="[1]", document_name="Parental Leave Policy", page=1, chunk_id="c1")]
    return QueryResult(
        question="How many weeks of leave?",
        answer=answer,
        citations=citations,
        retrieved_chunks=retrieved,
        strategy="fixed_vector",
        latency_ms=42.0,
    )


# --- AnswerEvaluator ---

def test_answer_evaluator_parses_scores():
    fake = FakeJudgeClient('{"correctness": 5, "relevance": 4, "completeness": 5, "rationale": "good"}')
    evaluator = AnswerEvaluator(llm_client=fake)
    question = EvalQuestion(
        id="q1",
        question="How many weeks?",
        relevant_document_ids=["parental_leave_policy"],
        expected_answer="Sixteen weeks.",
    )

    scores = evaluator.evaluate(_make_result(), question)

    assert scores.correctness == 5
    assert scores.relevance == 4
    assert scores.rationale == "good"


def test_answer_evaluator_requires_expected_answer():
    evaluator = AnswerEvaluator(llm_client=FakeJudgeClient("{}"))
    question = EvalQuestion(id="q1", question="q", relevant_document_ids=["doc_a"])  # no expected_answer

    with pytest.raises(ValueError):
        evaluator.evaluate(_make_result(), question)


# --- GroundingEvaluator ---

def test_grounding_evaluator_parses_scores():
    fake = FakeJudgeClient('{"faithfulness": 5, "likely_hallucination": false, "rationale": "supported"}')
    evaluator = GroundingEvaluator(llm_client=fake)

    scores = evaluator.evaluate(_make_result())

    assert scores.faithfulness == 5
    assert scores.likely_hallucination is False


def test_grounding_evaluator_flags_hallucination():
    fake = FakeJudgeClient('{"faithfulness": 1, "likely_hallucination": true, "rationale": "invented"}')
    evaluator = GroundingEvaluator(llm_client=fake)

    scores = evaluator.evaluate(_make_result())

    assert scores.likely_hallucination is True


# --- EvaluationRunner ---

def _build_fake_pipeline(tmp_path: Path, llm_client) -> RAGPipeline:
    chunk = Chunk(
        chunk_id="parental_leave_policy_000",
        document_id="parental_leave_policy",
        document_name="Parental Leave Policy",
        department="hr",
        page=1,
        chunk_index=0,
        text="Employees get sixteen weeks of paid parental leave.",
    )
    embedder = HashingEmbedder()
    store = VectorStore()
    store.build([chunk], embedder.embed_texts([chunk.text]))
    store.save(tmp_path / "vector_store")

    settings = Settings(
        embedding_backend="hashing",
        vector_store_dir=str(tmp_path / "vector_store"),
        groq_api_key="fake-key",
        _env_file=None,
    )
    return RAGPipeline(
        settings=settings,
        strategy=StrategyConfig(top_k=2),
        answer_generator=AnswerGenerator(llm_client=llm_client),
    )


def test_evaluation_runner_with_llm_judges():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        pipeline = _build_fake_pipeline(tmp_path, FakeJudgeClient("Sixteen weeks [1]."))

        judge_client = FakeJudgeClient(
            '{"correctness": 5, "relevance": 5, "completeness": 5, "rationale": "ok", '
            '"faithfulness": 5, "likely_hallucination": false}'
        )
        runner = EvaluationRunner(
            pipeline,
            answer_evaluator=AnswerEvaluator(llm_client=judge_client),
            grounding_evaluator=GroundingEvaluator(llm_client=judge_client),
        )
        dataset = EvalDataset(
            questions=[
                EvalQuestion(
                    id="q1",
                    question="How many weeks of leave?",
                    relevant_document_ids=["parental_leave_policy"],
                    expected_answer="Sixteen weeks.",
                )
            ]
        )

        report = runner.run(dataset)

        assert len(report.results) == 1
        r = report.results[0]
        assert r.retrieval.recall_at_k == 1.0
        assert r.citation.citation_accuracy == 1.0
        assert r.answer_judge.correctness == 5
        assert r.grounding_judge.faithfulness == 5
        assert r.judge_error is None

        agg = report.aggregate()
        assert agg["num_questions"] == 1
        assert agg["avg_recall_at_k"] == 1.0
        assert "avg_correctness" in agg


def test_evaluation_runner_without_llm_judges():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        pipeline = _build_fake_pipeline(tmp_path, FakeJudgeClient("Sixteen weeks [1]."))

        runner = EvaluationRunner(pipeline, run_llm_judges=False)
        dataset = EvalDataset(
            questions=[
                EvalQuestion(
                    id="q1",
                    question="How many weeks of leave?",
                    relevant_document_ids=["parental_leave_policy"],
                )
            ]
        )

        report = runner.run(dataset)

        assert report.results[0].answer_judge is None
        assert report.results[0].grounding_judge is None
        agg = report.aggregate()
        assert "avg_correctness" not in agg


def test_evaluation_runner_isolates_judge_failures():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        pipeline = _build_fake_pipeline(tmp_path, FakeJudgeClient("Sixteen weeks [1]."))

        failing_client = FailingJudgeClient()
        runner = EvaluationRunner(
            pipeline,
            answer_evaluator=AnswerEvaluator(llm_client=failing_client),
            grounding_evaluator=GroundingEvaluator(llm_client=failing_client),
        )
        dataset = EvalDataset(
            questions=[
                EvalQuestion(
                    id="q1",
                    question="How many weeks of leave?",
                    relevant_document_ids=["parental_leave_policy"],
                    expected_answer="Sixteen weeks.",
                )
            ]
        )

        # Should not raise, even though the judge call fails.
        report = runner.run(dataset)

        assert report.results[0].answer_judge is None
        assert report.results[0].judge_error is not None
        # Deterministic metrics still computed despite the judge failure.
        assert report.results[0].retrieval.recall_at_k == 1.0


def test_evaluation_runner_isolates_generation_failures():
    """If the pipeline's own answer-generation call fails for one
    question (not a judge call — the actual RAG answer), that question
    should be recorded with `error` set, and the run should continue to
    other questions rather than crash entirely."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        pipeline = _build_fake_pipeline(tmp_path, FailingJudgeClient())  # generation itself fails

        runner = EvaluationRunner(pipeline, run_llm_judges=False)
        dataset = EvalDataset(
            questions=[
                EvalQuestion(
                    id="q1",
                    question="How many weeks of leave?",
                    relevant_document_ids=["parental_leave_policy"],
                )
            ]
        )

        report = runner.run(dataset)

        assert report.results[0].error is not None
        assert report.results[0].retrieval is None
        assert report.results[0].answer is None

        agg = report.aggregate()
        assert agg["num_questions"] == 1
        assert agg["num_errors"] == 1


def test_evaluation_runner_disables_judges_when_construction_fails(monkeypatch):
    """If AnswerEvaluator()/GroundingEvaluator() can't even be built (e.g.
    no GROQ_API_KEY at all), the runner should disable LLM-judge metrics
    for the whole run rather than crash — deterministic metrics still work."""
    import app.evaluation.runner as runner_module

    def _raise(*args, **kwargs):
        raise RuntimeError("GROQ_API_KEY is not configured.")

    monkeypatch.setattr(runner_module, "AnswerEvaluator", _raise)
    monkeypatch.setattr(runner_module, "GroundingEvaluator", _raise)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        pipeline = _build_fake_pipeline(tmp_path, FakeJudgeClient("Sixteen weeks [1]."))

        runner = EvaluationRunner(pipeline)  # no evaluators injected -> tries to auto-build, fails, disables

        assert runner.run_llm_judges is False

        dataset = EvalDataset(
            questions=[
                EvalQuestion(
                    id="q1",
                    question="How many weeks of leave?",
                    relevant_document_ids=["parental_leave_policy"],
                    expected_answer="Sixteen weeks.",
                )
            ]
        )
        report = runner.run(dataset)
        assert report.results[0].answer_judge is None
        assert report.results[0].retrieval.recall_at_k == 1.0  # deterministic metrics unaffected


if __name__ == "__main__":
    test_answer_evaluator_parses_scores()
    test_answer_evaluator_requires_expected_answer()
    test_grounding_evaluator_parses_scores()
    test_grounding_evaluator_flags_hallucination()
    test_evaluation_runner_with_llm_judges()
    test_evaluation_runner_without_llm_judges()
    test_evaluation_runner_isolates_judge_failures()
    test_evaluation_runner_isolates_generation_failures()
    print("✅ All LLM-judge and runner tests passed. (run construction-failure test via pytest for monkeypatch)")
