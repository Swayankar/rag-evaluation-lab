import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app.evaluation.dataset import EvalQuestion, load_eval_dataset, write_starter_template
from app.evaluation.evaluators.citation import CitationEvaluator
from app.evaluation.metrics.answer_metrics import parse_json_response
from app.evaluation.metrics.retrieval_metrics import (
    mean_reciprocal_rank,
    precision_at_k,
    recall_at_k,
)
from app.models.document import Chunk
from app.models.query import Citation, QueryResult, RetrievedChunk


def _make_retrieved(document_id: str, chunk_id: str) -> RetrievedChunk:
    chunk = Chunk(
        chunk_id=chunk_id,
        document_id=document_id,
        document_name=document_id.title(),
        department="hr",
        page=1,
        chunk_index=0,
        text="filler text",
    )
    return RetrievedChunk(chunk=chunk, score=0.9)


# --- retrieval_metrics ---

def test_recall_at_k_full_and_partial():
    retrieved = ["doc_a", "doc_b", "doc_c"]
    assert recall_at_k(retrieved, ["doc_a"], k=3) == 1.0
    assert recall_at_k(retrieved, ["doc_a", "doc_z"], k=3) == 0.5
    assert recall_at_k(retrieved, [], k=3) == 0.0


def test_recall_at_k_respects_k_cutoff():
    retrieved = ["doc_z", "doc_z", "doc_a"]
    assert recall_at_k(retrieved, ["doc_a"], k=2) == 0.0
    assert recall_at_k(retrieved, ["doc_a"], k=3) == 1.0


def test_precision_at_k():
    retrieved = ["doc_a", "doc_z", "doc_b"]
    assert precision_at_k(retrieved, ["doc_a", "doc_b"], k=3) == pytest.approx(2 / 3)
    assert precision_at_k([], ["doc_a"], k=3) == 0.0


def test_mean_reciprocal_rank():
    assert mean_reciprocal_rank(["doc_z", "doc_a"], ["doc_a"]) == 0.5
    assert mean_reciprocal_rank(["doc_a"], ["doc_a"]) == 1.0
    assert mean_reciprocal_rank(["doc_z"], ["doc_a"]) == 0.0


# --- CitationEvaluator ---

def test_citation_evaluator_no_citations():
    result = QueryResult(
        question="q", answer="a", citations=[], retrieved_chunks=[], strategy="s", latency_ms=1.0
    )
    question = EvalQuestion(id="q1", question="q", relevant_document_ids=["doc_a"])

    scores = CitationEvaluator().evaluate(result, question)
    assert scores.citation_accuracy is None
    assert scores.num_citations == 0


def test_citation_evaluator_all_correct():
    retrieved = [_make_retrieved("doc_a", "c1")]
    citations = [Citation(marker="[1]", document_name="Doc A", page=1, chunk_id="c1")]
    result = QueryResult(
        question="q", answer="a", citations=citations, retrieved_chunks=retrieved, strategy="s", latency_ms=1.0
    )
    question = EvalQuestion(id="q1", question="q", relevant_document_ids=["doc_a"])

    scores = CitationEvaluator().evaluate(result, question)
    assert scores.citation_accuracy == 1.0
    assert scores.num_citations == 1


def test_citation_evaluator_wrong_document():
    retrieved = [_make_retrieved("doc_wrong", "c1")]
    citations = [Citation(marker="[1]", document_name="Doc Wrong", page=1, chunk_id="c1")]
    result = QueryResult(
        question="q", answer="a", citations=citations, retrieved_chunks=retrieved, strategy="s", latency_ms=1.0
    )
    question = EvalQuestion(id="q1", question="q", relevant_document_ids=["doc_a"])

    scores = CitationEvaluator().evaluate(result, question)
    assert scores.citation_accuracy == 0.0


def test_citation_evaluator_mixed_accuracy():
    retrieved = [_make_retrieved("doc_a", "c1"), _make_retrieved("doc_wrong", "c2")]
    citations = [
        Citation(marker="[1]", document_name="Doc A", page=1, chunk_id="c1"),
        Citation(marker="[2]", document_name="Doc Wrong", page=1, chunk_id="c2"),
    ]
    result = QueryResult(
        question="q", answer="a", citations=citations, retrieved_chunks=retrieved, strategy="s", latency_ms=1.0
    )
    question = EvalQuestion(id="q1", question="q", relevant_document_ids=["doc_a"])

    scores = CitationEvaluator().evaluate(result, question)
    assert scores.citation_accuracy == 0.5


# --- dataset ---

def test_eval_dataset_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "questions.json"
        write_starter_template(path)
        dataset = load_eval_dataset(path)

        assert len(dataset) == 3
        assert dataset.questions[0].id == "q1"
        assert dataset.questions[0].relevant_document_ids == ["parental_leave_policy"]


# --- answer_metrics JSON parsing ---

def test_parse_json_response_plain():
    data = parse_json_response('{"correctness": 5, "relevance": 4}')
    assert data == {"correctness": 5, "relevance": 4}


def test_parse_json_response_wrapped_in_markdown_fence():
    text = 'Sure, here is my score:\n```json\n{"faithfulness": 3, "likely_hallucination": false}\n```'
    data = parse_json_response(text)
    assert data["faithfulness"] == 3
    assert data["likely_hallucination"] is False


def test_parse_json_response_raises_on_no_json():
    with pytest.raises(ValueError):
        parse_json_response("I refuse to answer in JSON.")


if __name__ == "__main__":
    test_recall_at_k_full_and_partial()
    test_recall_at_k_respects_k_cutoff()
    test_precision_at_k()
    test_mean_reciprocal_rank()
    test_citation_evaluator_no_citations()
    test_citation_evaluator_all_correct()
    test_citation_evaluator_wrong_document()
    test_citation_evaluator_mixed_accuracy()
    test_eval_dataset_roundtrip()
    test_parse_json_response_plain()
    test_parse_json_response_wrapped_in_markdown_fence()
    print("✅ All deterministic evaluation tests passed.")
