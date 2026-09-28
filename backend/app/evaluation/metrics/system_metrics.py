"""
System-level metrics: latency (already measured end-to-end in
QueryResult) and approximate token usage.
"""
from dataclasses import dataclass

from app.models.query import QueryResult
from app.utils.token_counter import count_tokens


@dataclass
class SystemScores:
    latency_ms: float
    approx_prompt_tokens: int
    approx_completion_tokens: int


def compute_system_scores(result: QueryResult, prompt_text: str) -> SystemScores:
    return SystemScores(
        latency_ms=result.latency_ms,
        approx_prompt_tokens=count_tokens(prompt_text),
        approx_completion_tokens=count_tokens(result.answer),
    )