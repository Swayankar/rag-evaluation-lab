"""
Request/response shapes for the HTTP API. Kept separate from
app/models/query.py (the internal pipeline schemas) so the API contract
can evolve independently of internal representations.
"""
from typing import Literal

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, examples=["How many weeks of parental leave do employees get?"])
    top_k: int | None = Field(default=None, ge=1, le=20, description="Override the default retrieval top_k")
    retrieval_strategy: Literal["vector", "bm25", "hybrid", "hybrid_rerank"] | None = Field(
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


class DocumentSummary(BaseModel):
    document_id: str
    document_name: str
    department: str
    year: int | None
    chunk_count: int


class DocumentsResponse(BaseModel):
    documents: list[DocumentSummary]
    total_chunks: int
