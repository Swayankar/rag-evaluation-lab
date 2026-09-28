"""
Deterministic citation-accuracy check: of the citations the model
actually used (already parsed and validated by AnswerGenerator — see
app/generation/answer_generator.py), what fraction point at a document
we consider relevant for this question?

This is a structural check, not a semantic one — it doesn't verify the
cited text actually supports the specific claim next to it (that's
GroundingEvaluator's job, via an LLM judge). It answers a narrower, but
free and deterministic, question: is the model citing the right
documents at all?
"""
from dataclasses import dataclass

from app.evaluation.dataset import EvalQuestion
from app.models.query import QueryResult


@dataclass
class CitationScores:
    citation_accuracy: float | None  # None if the answer cited nothing
    num_citations: int


class CitationEvaluator:
    def evaluate(self, result: QueryResult, question: EvalQuestion) -> CitationScores:
        if not result.citations:
            return CitationScores(citation_accuracy=None, num_citations=0)

        relevant = set(question.relevant_document_ids)
        chunk_by_id = {r.chunk.chunk_id: r.chunk for r in result.retrieved_chunks}

        correct = 0
        for citation in result.citations:
            chunk = chunk_by_id.get(citation.chunk_id)
            if chunk is not None and chunk.document_id in relevant:
                correct += 1

        return CitationScores(
            citation_accuracy=correct / len(result.citations),
            num_citations=len(result.citations),
        )
