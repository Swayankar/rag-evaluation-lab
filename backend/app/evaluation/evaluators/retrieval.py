"""
Wraps the pure retrieval_metrics functions to operate directly on a
QueryResult's retrieved_chunks and an EvalQuestion's ground truth.
"""
from dataclasses import dataclass

from app.evaluation.dataset import EvalQuestion
from app.evaluation.metrics.retrieval_metrics import (
    mean_reciprocal_rank,
    precision_at_k,
    recall_at_k,
)
from app.models.query import QueryResult


@dataclass
class RetrievalScores:
    recall_at_k: float
    precision_at_k: float
    mrr: float


class RetrievalEvaluator:
    def __init__(self, k: int = 5):
        self.k = k

    def evaluate(self, result: QueryResult, question: EvalQuestion) -> RetrievalScores:
        retrieved_document_ids = [r.chunk.document_id for r in result.retrieved_chunks]
        return RetrievalScores(
            recall_at_k=recall_at_k(retrieved_document_ids, question.relevant_document_ids, self.k),
            precision_at_k=precision_at_k(retrieved_document_ids, question.relevant_document_ids, self.k),
            mrr=mean_reciprocal_rank(retrieved_document_ids, question.relevant_document_ids),
        )
