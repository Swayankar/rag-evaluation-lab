"""
Orchestrates one generation step: build the prompt from retrieved chunks,
call the LLM, and parse the [N] markers it used back into structured
Citation objects pointing at real chunks/documents/pages.
"""

import re
import time

from app.core.logging import get_logger
from app.generation.llm import GroqClient
from app.generation.prompts import SYSTEM_PROMPT, build_user_prompt
from app.models.query import Citation, QueryResult, RetrievedChunk

logger = get_logger(__name__)

_CITATION_RE = re.compile(r"[\[【](\d+)[\]】]")


class AnswerGenerator:
    def __init__(self, llm_client: GroqClient | None = None):
        self.llm_client = llm_client or GroqClient()

    def generate(
        self,
        question: str,
        retrieved: list[RetrievedChunk],
        strategy: str = "fixed+vector",
    ) -> QueryResult:
        start = time.perf_counter()

        user_prompt = build_user_prompt(question, retrieved)

        answer_text = self.llm_client.chat(
            SYSTEM_PROMPT,
            user_prompt,
        )

        latency_ms = (time.perf_counter() - start) * 1000

        citations = self._extract_citations(
            answer_text,
            retrieved,
        )

        return QueryResult(
            question=question,
            answer=answer_text,
            citations=citations,
            retrieved_chunks=retrieved,
            strategy=strategy,
            latency_ms=latency_ms,
        )

    @staticmethod
    def _extract_citations(
        answer_text: str,
        retrieved: list[RetrievedChunk],
    ) -> list[Citation]:

        cited_indices = sorted(
            {int(m) for m in _CITATION_RE.findall(answer_text)}
        )

        citations: list[Citation] = []

        for idx in cited_indices:
            if 1 <= idx <= len(retrieved):
                chunk = retrieved[idx - 1].chunk

                citations.append(
                    Citation(
                        marker=f"[{idx}]",
                        document_name=chunk.document_name,
                        page=chunk.page,
                        chunk_id=chunk.chunk_id,
                    )
                )
            else:
                logger.warning(
                    "Model cited [%d] but only %d sources were retrieved — ignoring",
                    idx,
                    len(retrieved),
                )

        return citations