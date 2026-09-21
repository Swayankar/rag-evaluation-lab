from typing import Optional

from pydantic import BaseModel, Field


class RawPage(BaseModel):
    """One extracted page of text, before chunking."""

    document_id: str
    document_name: str
    department: str
    page: int
    text: str


class Chunk(BaseModel):
    """A single chunk, ready for embedding/storage. Matches the metadata
    shape described in the architecture doc."""

    chunk_id: str
    document_id: str
    document_name: str
    department: str
    year: Optional[int] = None
    page: int
    chunk_index: int
    chunking_strategy: str = Field(default="fixed")
    text: str
