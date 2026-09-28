"""
LLM-as-judge evaluator for answer correctness/relevance/completeness,
scored against the dataset's reference answer. Needs one Groq call per
question — EvaluationRunner isolates failures here so one bad judge
call doesn't take down the whole evaluation run.
"""
from dataclasses import dataclass

from app.evaluation.dataset import EvalQuestion
from app.evaluation.metrics.answer_metrics import (
    ANSWER_JUDGE_SYSTEM_PROMPT,
    build_answer_judge_prompt,
    parse_json_response,
)
from app.generation.llm import GroqClient
from app.models.query import QueryResult


@dataclass
class AnswerScores:
    correctness: float
    relevance: float
    completeness: float
    rationale: str


class AnswerEvaluator:
    def __init__(self, llm_client: GroqClient | None = None):
        self.llm_client = llm_client or GroqClient()

    def evaluate(self, result: QueryResult, question: EvalQuestion) -> AnswerScores:
        if not question.expected_answer:
            raise ValueError(
                f"Question {question.id!r} has no expected_answer to judge against"
            )
        prompt = build_answer_judge_prompt(
            question.question, question.expected_answer, result.answer
        )
        response_text = self.llm_client.chat(ANSWER_JUDGE_SYSTEM_PROMPT, prompt, temperature=0.0)
        data = parse_json_response(response_text)
        return AnswerScores(
            correctness=float(data["correctness"]),
            relevance=float(data["relevance"]),
            completeness=float(data["completeness"]),
            rationale=data.get("rationale", ""),
        )
