"""
Request/response shapes for the HTTP API. Kept separate from
app/models/query.py (the internal pipeline schemas) so the API contract
can evolve independently of internal representations.
"""
from typing import Literal

from pydantic import BaseModel, Field

ChunkingName = Literal["fixed", "semantic"]
RetrievalName = Literal["vector", "bm25", "hybrid", "hybrid_rerank"]


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, examples=["How many weeks of parental leave do employees get?"])
    top_k: int | None = Field(default=None, ge=1, le=20, description="Override the default retrieval top_k")
    chunking_strategy: ChunkingName | None = Field(
        default=None,
        description="Which chunked corpus to search (defaults to fixed)",
    )
    retrieval_strategy: RetrievalName | None = Field(
        default=None,
        description="Override the default retrieval strategy (defaults to plain vector search)",
    )


class CitationResponse(BaseModel):
    marker: str
    document_name: str
    page: int
    chunk_id: str


class RetrievedChunkResponse(BaseModel):
    chunk_id: str
    document_name: str
    department: str
    page: int
    score: float
    text: str


class QueryResponse(BaseModel):
    question: str
    answer: str
    citations: list[CitationResponse]
    retrieved_chunks: list[RetrievedChunkResponse]
    strategy: str
    latency_ms: float
    chunking_strategy: str | None = None
    retrieval_strategy: str | None = None


class StrategyChoice(BaseModel):
    chunking_strategy: ChunkingName = "fixed"
    retrieval_strategy: RetrievalName = "vector"


class CompareRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=20)
    strategies: list[StrategyChoice] | None = Field(
        default=None,
        max_length=8,
        description="Combinations to run. Omit (or null) to run every chunking x retrieval combination.",
    )


class CompareItem(BaseModel):
    """One strategy's outcome. Exactly one of `result` / `error` is set, so a
    strategy that isn't built yet (or whose LLM call failed) never takes the
    other strategies down with it."""

    strategy_name: str
    chunking_strategy: str
    retrieval_strategy: str
    result: QueryResponse | None = None
    error: str | None = None


class CompareResponse(BaseModel):
    question: str
    results: list[CompareItem]
    total_latency_ms: float


class DocumentSummary(BaseModel):
    document_id: str
    document_name: str
    department: str
    year: int | None
    chunk_count: int


class DocumentsResponse(BaseModel):
    documents: list[DocumentSummary]
    total_chunks: int
