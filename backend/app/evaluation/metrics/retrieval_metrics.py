"""
Pure retrieval metrics: no I/O, no LLM calls, fully deterministic and
trivial to unit test. All three operate on document-level relevance
(see dataset.py for why), comparing the retrieved chunks' document_ids
against a question's ground-truth relevant_document_ids.
"""

def recall_at_k(retrieved_document_ids: list[str], relevant_document_ids: list[str], k: int) -> float:
    """Of all the documents that SHOULD have been retrieved, what
    fraction actually showed up in the top K?"""
    relevant_set = set(relevant_document_ids)
    if not relevant_set:
        return 0.0
    top_k = set(retrieved_document_ids[:k])
    hits = len(top_k & relevant_set)
    return hits / len(relevant_set)


def precision_at_k(retrieved_document_ids: list[str], relevant_document_ids: list[str], k: int) -> float:
    """Of the top K documents retrieved, what fraction were actually
    relevant?"""
    top_k = retrieved_document_ids[:k]
    if not top_k:
        return 0.0
    relevant_set = set(relevant_document_ids)
    hits = sum(1 for doc_id in top_k if doc_id in relevant_set)
    return hits / len(top_k)


def mean_reciprocal_rank(retrieved_document_ids: list[str], relevant_document_ids: list[str]) -> float:
    """1 / (rank of the first relevant document), or 0 if none of the
    retrieved documents were relevant. Named "mean" because it's usually
    averaged across many questions — this function computes it for one."""
    relevant_set = set(relevant_document_ids)
    for rank, doc_id in enumerate(retrieved_document_ids, start=1):
        if doc_id in relevant_set:
            return 1.0 / rank
    return 0.0
