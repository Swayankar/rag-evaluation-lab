"""
BM25 lexical search over chunk text — complements vector search. Good
at exact terms, numbers, and codes ("Section 4.2", "twelve characters",
"ninety days") that a semantic embedding can blur past in favor of a
topically-similar-but-wrong chunk.
"""
import json
import re
from pathlib import Path

from rank_bm25 import BM25Okapi

from app.core.logging import get_logger
from app.models.document import Chunk
from app.models.query import RetrievedChunk
from app.retrieval.base import BaseRetriever

logger = get_logger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class BM25Retriever(BaseRetriever):
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        tokenized_corpus = [_tokenize(c.text) for c in chunks]
        self._bm25 = BM25Okapi(tokenized_corpus) if tokenized_corpus else None

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        k = min(top_k, len(scores))
        ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        return [
            RetrievedChunk(chunk=self.chunks[i], score=float(scores[i]))
            for i in ranked_indices
        ]

    def __len__(self) -> int:
        return len(self.chunks)

    @classmethod
    def from_chunks_file(cls, path: Path) -> "BM25Retriever":
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        chunks = [Chunk(**d) for d in data]
        logger.info("Built BM25 index over %d chunks from %s", len(chunks), path)
        return cls(chunks)
