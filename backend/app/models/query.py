from pydantic import BaseModel

from app.models.document import Chunk


class RetrievedChunk(BaseModel):
    """A chunk plus the similarity score it was retrieved with."""

    chunk: Chunk
    score: float


class Citation(BaseModel):
    """A source the LLM actually cited in its answer (parsed out of the
    [N] markers it was instructed to use)."""

    marker: str
    document_name: str
    page: int
    chunk_id: str


class QueryResult(BaseModel):
    question: str
    answer: str
    citations: list[Citation]
    retrieved_chunks: list[RetrievedChunk]
    strategy: str
    latency_ms: float
