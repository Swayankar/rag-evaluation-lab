"""
Runs an evaluation dataset through a RAGPipeline and produces a report.

Every failure mode is isolated to the single question that hit it, so
one bad call never aborts the whole run:
  - If the pipeline itself fails to answer a question (the RAG
    pipeline's own Groq call — rate limit, bad key, network issue), that
    question is recorded with `error` set and no scores, and the run
    continues to the next question.
  - If an LLM-judge call fails for a question that DID get an answer
    (a separate, second set of Groq calls purely for scoring), that
    question keeps its deterministic scores (retrieval/citation/system)
    and just has `judge_error` set instead of `answer_judge`/`grounding_judge`.
  - If the judge evaluators can't even be constructed (e.g. no
    GROQ_API_KEY at all), LLM-judge metrics are disabled for the whole
    run up front, with a clear warning — retrieval/citation metrics
    still run normally.
"""
from dataclasses import dataclass, field

from app.core.logging import get_logger
from app.evaluation.dataset import EvalDataset, EvalQuestion
from app.evaluation.evaluators.answer import AnswerEvaluator, AnswerScores
from app.evaluation.evaluators.citation import CitationEvaluator, CitationScores
from app.evaluation.evaluators.grounding import GroundingEvaluator, GroundingScores
from app.evaluation.evaluators.retrieval import RetrievalEvaluator, RetrievalScores
from app.evaluation.metrics.system_metrics import SystemScores, compute_system_scores
from app.generation.prompts import build_user_prompt
from app.pipelines.rag_pipeline import RAGPipeline

logger = get_logger(__name__)


@dataclass
class QuestionResult:
    question_id: str
    question: str
    answer: str | None = None
    retrieval: RetrievalScores | None = None
    citation: CitationScores | None = None
    system: SystemScores | None = None
    answer_judge: AnswerScores | None = None
    grounding_judge: GroundingScores | None = None
    judge_error: str | None = None
    error: str | None = None


@dataclass
class EvaluationReport:
    strategy_name: str
    results: list[QuestionResult] = field(default_factory=list)

    def aggregate(self) -> dict:
        scored = [r for r in self.results if r.error is None]
        num_errors = len(self.results) - len(scored)

        if not scored:
            return {"num_questions": len(self.results), "num_errors": num_errors}

        n = len(scored)
        agg: dict = {
            "num_questions": len(self.results),
            "avg_recall_at_k": sum(r.retrieval.recall_at_k for r in scored) / n,
            "avg_precision_at_k": sum(r.retrieval.precision_at_k for r in scored) / n,
            "avg_mrr": sum(r.retrieval.mrr for r in scored) / n,
            "avg_latency_ms": sum(r.system.latency_ms for r in scored) / n,
            "avg_prompt_tokens": sum(r.system.approx_prompt_tokens for r in scored) / n,
        }
        if num_errors:
            agg["num_errors"] = num_errors

        citation_scores = [
            r.citation.citation_accuracy for r in scored if r.citation.citation_accuracy is not None
        ]
        if citation_scores:
            agg["avg_citation_accuracy"] = sum(citation_scores) / len(citation_scores)

        judged = [r.answer_judge for r in scored if r.answer_judge is not None]
        if judged:
            agg["avg_correctness"] = sum(j.correctness for j in judged) / len(judged)
            agg["avg_relevance"] = sum(j.relevance for j in judged) / len(judged)
            agg["avg_completeness"] = sum(j.completeness for j in judged) / len(judged)

        grounded = [r.grounding_judge for r in scored if r.grounding_judge is not None]
        if grounded:
            agg["avg_faithfulness"] = sum(g.faithfulness for g in grounded) / len(grounded)
            agg["hallucination_rate"] = sum(1 for g in grounded if g.likely_hallucination) / len(grounded)

        num_judge_errors = sum(1 for r in scored if r.judge_error)
        if num_judge_errors:
            agg["num_judge_errors"] = num_judge_errors

        return agg


class EvaluationRunner:
    def __init__(
        self,
        pipeline: RAGPipeline,
        retrieval_evaluator: RetrievalEvaluator | None = None,
        citation_evaluator: CitationEvaluator | None = None,
        answer_evaluator: AnswerEvaluator | None = None,
        grounding_evaluator: GroundingEvaluator | None = None,
        run_llm_judges: bool = True,
    ):
        self.pipeline = pipeline
        self.retrieval_evaluator = retrieval_evaluator or RetrievalEvaluator(k=pipeline.strategy.top_k)
        self.citation_evaluator = citation_evaluator or CitationEvaluator()

        self.run_llm_judges = run_llm_judges
        self.answer_evaluator = answer_evaluator
        self.grounding_evaluator = grounding_evaluator

        if self.run_llm_judges and self.answer_evaluator is None:
            try:
                self.answer_evaluator = AnswerEvaluator()
            except Exception as exc:  # noqa: BLE001 - construction failure disables judges, doesn't crash
                logger.warning("Disabling LLM-judge metrics — could not build AnswerEvaluator (%s)", exc)
                self.run_llm_judges = False

        if self.run_llm_judges and self.grounding_evaluator is None:
            try:
                self.grounding_evaluator = GroundingEvaluator()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Disabling LLM-judge metrics — could not build GroundingEvaluator (%s)", exc)
                self.run_llm_judges = False

    def run(self, dataset: EvalDataset) -> EvaluationReport:
        report = EvaluationReport(strategy_name=self.pipeline.strategy.name)
        for question in dataset.questions:
            logger.info("Evaluating question %s: %r", question.id, question.question)
            report.results.append(self._evaluate_one(question))
        return report

    def _evaluate_one(self, question: EvalQuestion) -> QuestionResult:
        try:
            result = self.pipeline.answer(question.question)
        except Exception as exc:  # noqa: BLE001 - isolate generation failures per-question too
            logger.warning("Pipeline failed to answer question %r: %s", question.id, exc)
            return QuestionResult(question_id=question.id, question=question.question, error=str(exc))

        retrieval_scores = self.retrieval_evaluator.evaluate(result, question)
        citation_scores = self.citation_evaluator.evaluate(result, question)
        prompt_text = build_user_prompt(question.question, result.retrieved_chunks)
        system_scores = compute_system_scores(result, prompt_text)

        answer_judge = None
        grounding_judge = None
        judge_error = None
        if self.run_llm_judges:
            try:
                if question.expected_answer:
                    answer_judge = self.answer_evaluator.evaluate(result, question)
                grounding_judge = self.grounding_evaluator.evaluate(result)
            except Exception as exc:  # noqa: BLE001 - isolate judge failures per-question
                judge_error = str(exc)
                logger.warning("LLM judge failed for question %r: %s", question.id, exc)

        return QuestionResult(
            question_id=question.id,
            question=question.question,
            answer=result.answer,
            retrieval=retrieval_scores,
            citation=citation_scores,
            system=system_scores,
            answer_judge=answer_judge,
            grounding_judge=grounding_judge,
            judge_error=judge_error,
        )
