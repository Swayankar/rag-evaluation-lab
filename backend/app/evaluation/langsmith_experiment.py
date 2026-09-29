"""
LangSmith experiments: run the evaluation dataset through a RAGPipeline
and record the results as a named experiment in LangSmith, where runs on
the same dataset can be compared side by side in the UI.

This is a *second front-end*, not a second implementation. Each LangSmith evaluator 
below is a thin adapter that rebuilds a QueryResult/EvalQuestion from LangSmith's 
inputs/outputs and calls the same RetrievalEvaluator / CitationEvaluator / AnswerEvaluator /
GroundingEvaluator used by the local runner — so a metric can't quietly
mean one thing locally and another in LangSmith.

Datasets are versioned by content: the LangSmith dataset name includes a
short hash of questions.json. Edit a question and you get a *new* dataset
rather than experiments silently comparing runs made on different
questions under one name — which is the failure mode that makes
experiment comparisons untrustworthy.
"""
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable

from app.core.config import Settings
from app.core.logging import get_logger
from app.evaluation.dataset import EvalDataset, EvalQuestion
from app.evaluation.evaluators.answer import AnswerEvaluator
from app.evaluation.evaluators.citation import CitationEvaluator
from app.evaluation.evaluators.grounding import GroundingEvaluator
from app.evaluation.evaluators.retrieval import RetrievalEvaluator
from app.evaluation.metrics.system_metrics import compute_system_scores
from app.generation.prompts import build_user_prompt
from app.models.query import QueryResult
from app.pipelines.rag_pipeline import RAGPipeline
from app.tracing.langsmith import configure_tracing

logger = get_logger(__name__)

DATASET_BASE_NAME = "rag-evaluation-lab"


class LangSmithSetupError(RuntimeError):
    """Raised when LangSmith isn't configured well enough to run an experiment."""


# --------------------------------------------------------------------------
# Dataset sync
# --------------------------------------------------------------------------

def dataset_name_for(dataset: EvalDataset, base: str = DATASET_BASE_NAME) -> str:
    payload = json.dumps([q.model_dump() for q in dataset.questions], sort_keys=True)
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:8]
    return f"{base}-{digest}"


def _example_payload(q: EvalQuestion) -> dict:
    return {
        "inputs": {"question": q.question},
        "outputs": {
            "expected_answer": q.expected_answer,
            "relevant_document_ids": q.relevant_document_ids,
        },
        "metadata": {
            "question_id": q.id,
            "category": q.category,
            "expected_keywords": q.expected_keywords,
        },
    }


def ensure_dataset(client: Any, dataset: EvalDataset, name: str) -> bool:
    """Create the LangSmith dataset for this version of questions.json if it
    doesn't exist yet. Returns True if it was created, False if reused.

    If uploading the examples fails partway, the half-built dataset is
    deleted again (it was created moments ago, so this is safe) — otherwise
    the next run would find an existing-but-empty dataset and trust it."""
    if client.has_dataset(dataset_name=name):
        return False

    created = client.create_dataset(
        dataset_name=name,
        description=f"RAG Evaluation Lab questions ({len(dataset)} examples), synced from questions.json",
    )
    try:
        client.create_examples(
            dataset_id=created.id,
            examples=[_example_payload(q) for q in dataset.questions],
        )
    except Exception:
        try:
            client.delete_dataset(dataset_id=created.id)
        except Exception as cleanup_exc:  # noqa: BLE001
            logger.warning("Could not clean up partially-created dataset %r: %s", name, cleanup_exc)
        raise
    return True


# --------------------------------------------------------------------------
# Target + evaluator adapters
# --------------------------------------------------------------------------

def make_target(pipeline: RAGPipeline) -> Callable[[dict], dict]:
    def target(inputs: dict) -> dict:
        return pipeline.answer(inputs["question"]).model_dump()

    return target


def _query_result_or_none(outputs: dict) -> QueryResult | None:
    """LangSmith runs evaluators even on examples where the target raised,
    handing them outputs like {'output': None}. Treat that as 'nothing to
    score' — and, importantly, don't spend LLM-judge calls on it."""
    if not outputs or "answer" not in outputs or "retrieved_chunks" not in outputs:
        return None
    return QueryResult(**outputs)


def _question_from(inputs: dict, reference_outputs: dict) -> EvalQuestion:
    return EvalQuestion(
        id="langsmith-example",
        question=inputs["question"],
        relevant_document_ids=reference_outputs.get("relevant_document_ids") or [],
        expected_answer=reference_outputs.get("expected_answer"),
    )


_NOTHING = {"results": []}


def build_evaluators(
    top_k: int,
    run_llm_judges: bool = True,
    answer_evaluator: AnswerEvaluator | None = None,
    grounding_evaluator: GroundingEvaluator | None = None,
) -> list[Callable]:
    retrieval_ev = RetrievalEvaluator(k=top_k)
    citation_ev = CitationEvaluator()

    def retrieval_metrics(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
        result = _query_result_or_none(outputs)
        if result is None:
            return _NOTHING
        s = retrieval_ev.evaluate(result, _question_from(inputs, reference_outputs))
        return {
            "results": [
                {"key": "recall_at_k", "score": s.recall_at_k},
                {"key": "precision_at_k", "score": s.precision_at_k},
                {"key": "mrr", "score": s.mrr},
            ]
        }

    def citation_metrics(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
        result = _query_result_or_none(outputs)
        if result is None:
            return _NOTHING
        s = citation_ev.evaluate(result, _question_from(inputs, reference_outputs))
        results = [{"key": "num_citations", "score": float(s.num_citations)}]
        if s.citation_accuracy is not None:  # no citations -> accuracy is undefined, not 0
            results.append({"key": "citation_accuracy", "score": s.citation_accuracy})
        return {"results": results}

    def system_metrics(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
        result = _query_result_or_none(outputs)
        if result is None:
            return _NOTHING
        prompt = build_user_prompt(inputs["question"], result.retrieved_chunks)
        s = compute_system_scores(result, prompt)
        return {
            "results": [
                {"key": "latency_ms", "score": s.latency_ms},
                {"key": "approx_prompt_tokens", "score": float(s.approx_prompt_tokens)},
            ]
        }

    evaluators: list[Callable] = [retrieval_metrics, citation_metrics, system_metrics]

    if not run_llm_judges:
        return evaluators

    try:
        answer_ev = answer_evaluator or AnswerEvaluator()
        grounding_ev = grounding_evaluator or GroundingEvaluator()
    except Exception as exc:  # noqa: BLE001 - e.g. no GROQ_API_KEY: skip judges, keep the rest
        logger.warning("Skipping LLM-judge evaluators — could not build them (%s)", exc)
        return evaluators

    def answer_quality(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
        result = _query_result_or_none(outputs)
        question = _question_from(inputs, reference_outputs)
        if result is None or not question.expected_answer:
            return _NOTHING
        s = answer_ev.evaluate(result, question)
        comment = s.rationale
        return {
            "results": [
                {"key": "correctness", "score": s.correctness, "comment": comment},
                {"key": "relevance", "score": s.relevance},
                {"key": "completeness", "score": s.completeness},
            ]
        }

    def grounding(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
        result = _query_result_or_none(outputs)
        if result is None:
            return _NOTHING
        s = grounding_ev.evaluate(result)
        return {
            "results": [
                {"key": "faithfulness", "score": s.faithfulness, "comment": s.rationale},
                {"key": "hallucination", "score": 1.0 if s.likely_hallucination else 0.0},
            ]
        }

    evaluators.extend([answer_quality, grounding])
    return evaluators


# --------------------------------------------------------------------------
# Running an experiment
# --------------------------------------------------------------------------

@dataclass
class ExperimentSummary:
    experiment_name: str
    dataset_name: str
    num_examples: int
    num_target_errors: int
    averages: dict[str, float] = field(default_factory=dict)


def summarize_results(results: Any) -> tuple[int, int, dict[str, float]]:
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    num_examples = 0
    num_errors = 0

    for item in results:
        num_examples += 1
        if item["run"].error:
            num_errors += 1
            continue
        for r in (item["evaluation_results"] or {}).get("results", []):
            if r.score is None:
                continue
            sums[r.key] = sums.get(r.key, 0.0) + float(r.score)
            counts[r.key] = counts.get(r.key, 0) + 1

    return num_examples, num_errors, {k: sums[k] / counts[k] for k in sums}


def experiment_metadata(pipeline: RAGPipeline, run_llm_judges: bool) -> dict:
    s = pipeline.strategy
    meta: dict = {
        "strategy_name": s.name,
        "chunking_strategy": s.chunking_strategy,
        "retrieval_strategy": s.retrieval_strategy,
        "top_k": s.top_k,
        "llm_model": pipeline.settings.groq_model,
        "embedder": type(pipeline.embedder).__name__,
        "llm_judges": run_llm_judges,
    }
    reranker = getattr(pipeline.retriever, "reranker", None)
    if reranker is not None:
        meta["reranker"] = type(reranker).__name__
    return meta


def run_langsmith_experiment(
    pipeline: RAGPipeline,
    dataset: EvalDataset,
    settings: Settings,
    *,
    run_llm_judges: bool = True,
    trace_evaluators: bool = False,
    client: Any = None,
    data: Any = None,
    upload_results: bool = True,
    evaluators: list[Callable] | None = None,
) -> ExperimentSummary:
    """Run `dataset` through `pipeline` as a LangSmith experiment.

    `data`, `upload_results`, `evaluators` and `client` exist so tests can run
    the whole flow locally without network access; normal callers leave them
    alone."""
    from langsmith import Client, evaluate

    if upload_results:
        if not configure_tracing(settings, force=True):
            raise LangSmithSetupError(
                "LANGCHAIN_API_KEY is not set. Add your LangSmith key to .env "
                "(get one at https://smith.langchain.com -> Settings -> API Keys)."
            )
        dataset_name = dataset_name_for(dataset)
        try:
            client = client or Client()
            created = ensure_dataset(client, dataset, dataset_name)
        except Exception as exc:  # noqa: BLE001 - turn SDK/network errors into one actionable message
            raise LangSmithSetupError(
                f"Couldn't sync the dataset to LangSmith ({type(exc).__name__}: {str(exc)[:300]}).\n"
                "Check that LANGCHAIN_API_KEY is valid and that you have network access. If your "
                "LangSmith account is in the EU region, also set "
                "LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com in .env."
            ) from exc
        logger.info(
            "%s LangSmith dataset %r (%d examples)",
            "Created" if created else "Reusing", dataset_name, len(dataset),
        )
        data = dataset_name
    else:
        dataset_name = "(local, not uploaded)"

    meta = experiment_metadata(pipeline, run_llm_judges)
    evaluators = evaluators or build_evaluators(pipeline.strategy.top_k, run_llm_judges)

    results = evaluate(
        make_target(pipeline),
        data=data,
        evaluators=evaluators,
        experiment_prefix=pipeline.strategy.name,
        description=f"{pipeline.strategy.name}: chunking={meta['chunking_strategy']}, retrieval={meta['retrieval_strategy']}",
        metadata=meta,
        max_concurrency=0,  # sequential: Groq's free tier rate-limits parallel calls
        client=client,
        upload_results=upload_results,
        disable_evaluator_tracing=not trace_evaluators,
    )

    num_examples, num_errors, averages = summarize_results(results)
    return ExperimentSummary(
        experiment_name=results.experiment_name,
        dataset_name=dataset_name,
        num_examples=num_examples,
        num_target_errors=num_errors,
        averages=averages,
    )