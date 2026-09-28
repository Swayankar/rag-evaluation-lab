"""
LLM-as-judge evaluator for grounding: is the answer actually supported
by the retrieved context, or does it invent things not present in any
retrieved chunk (hallucination)?

Note on scope: "faithfulness" here checks the answer against whatever
was retrieved, not against absolute ground truth — an answer can be
perfectly faithful to irrelevant context and still be wrong. Pair this
with RetrievalEvaluator (was the right context even retrieved?) and
AnswerEvaluator (is the answer actually correct?) for the full picture;
none of the three alone tells you everything.
"""
from dataclasses import dataclass

from app.evaluation.metrics.answer_metrics import (
    FAITHFULNESS_JUDGE_SYSTEM_PROMPT,
    build_faithfulness_judge_prompt,
    parse_json_response,
)
from app.generation.llm import GroqClient
from app.models.query import QueryResult


@dataclass
class GroundingScores:
    faithfulness: float
    likely_hallucination: bool
    rationale: str


class GroundingEvaluator:
    def __init__(self, llm_client: GroqClient | None = None):
        self.llm_client = llm_client or GroqClient()

    def evaluate(self, result: QueryResult) -> GroundingScores:
        context = "\n\n".join(r.chunk.text for r in result.retrieved_chunks)
        prompt = build_faithfulness_judge_prompt(context, result.answer)
        response_text = self.llm_client.chat(
            FAITHFULNESS_JUDGE_SYSTEM_PROMPT, prompt, temperature=0.0
        )
        data = parse_json_response(response_text)
        return GroundingScores(
            faithfulness=float(data["faithfulness"]),
            likely_hallucination=bool(data.get("likely_hallucination", False)),
            rationale=data.get("rationale", ""),
        )
