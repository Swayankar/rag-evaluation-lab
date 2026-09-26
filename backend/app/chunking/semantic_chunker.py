"""
Strategy B: split into sentences, embed each
one, and start a new chunk wherever consecutive sentences' semantic
similarity drops sharply — a topic change — rather than at a fixed
token count. Ideally, boundaries land on natural section breaks
(Eligibility -> Duration -> Application Process -> Exceptions) instead
of mid-sentence or mid-idea.

Breakpoints are chosen adaptively per document: the distance (1 -
cosine similarity) between every consecutive sentence pair is computed,
and only the sharpest drops — those above breakpoint_percentile — become
chunk boundaries. This adapts to each document's own writing style
instead of using one fixed similarity cutoff for every document.

Small chunks are merged forward until they reach min_chunk_tokens, and
oversized ones are hard-split at max_chunk_tokens, so output sizes stay
in a comparable range to the fixed chunker's for a fair side-by-side
comparison.
"""
import re
from itertools import groupby

import numpy as np

from app.chunking.base import BaseChunker
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.embeddings.embedder import BaseEmbedder, get_embedder
from app.ingestion.cleaner import clean_text
from app.ingestion.metadata import extract_year
from app.models.document import Chunk, RawPage
from app.utils.token_counter import count_tokens

logger = get_logger(__name__)

# Split after sentence-ending punctuation, only when followed by
# whitespace + an uppercase letter or digit (a decent heuristic for
# policy-document prose without pulling in a full NLP sentence splitter).
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


def split_sentences(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]


class SemanticChunker(BaseChunker):
    strategy_name = "semantic"

    def __init__(
        self,
        embedder: BaseEmbedder | None = None,
        settings: Settings | None = None,
        breakpoint_percentile: float = 90.0,
        min_chunk_tokens: int = 150,
        max_chunk_tokens: int = 700,
    ):
        self.settings = settings or get_settings()
        self.embedder = embedder or get_embedder(self.settings)
        self.breakpoint_percentile = breakpoint_percentile
        self.min_chunk_tokens = min_chunk_tokens
        self.max_chunk_tokens = max_chunk_tokens

    def chunk_pages(self, pages: list[RawPage]) -> list[Chunk]:
        chunks: list[Chunk] = []
        for document_id, doc_pages in groupby(pages, key=lambda p: p.document_id):
            chunks.extend(self._chunk_single_document(list(doc_pages)))
        return chunks

    def _chunk_single_document(self, pages: list[RawPage]) -> list[Chunk]:
        if not pages:
            return []

        document_id = pages[0].document_id
        document_name = pages[0].document_name
        department = pages[0].department
        year = extract_year(document_id)

        sentences: list[str] = []
        sentence_pages: list[int] = []
        for page in pages:
            for sentence in split_sentences(clean_text(page.text)):
                sentences.append(sentence)
                sentence_pages.append(page.page)

        if not sentences:
            return []

        if len(sentences) == 1:
            groups = [[0]]
        else:
            embeddings = self.embedder.embed_texts(sentences)
            breakpoints = self._find_breakpoints(embeddings)
            groups = self._group_sentences(len(sentences), breakpoints)

        groups = self._enforce_size_bounds(groups, sentences)

        chunks = []
        for chunk_index, group in enumerate(groups):
            text = " ".join(sentences[i] for i in group)
            page_for_chunk = sentence_pages[group[0]]
            chunks.append(
                Chunk(
                    chunk_id=f"{document_id}_{chunk_index:03d}",
                    document_id=document_id,
                    document_name=document_name,
                    department=department,
                    year=year,
                    page=page_for_chunk,
                    chunk_index=chunk_index,
                    chunking_strategy=self.strategy_name,
                    text=text,
                )
            )
        return chunks

    def _find_breakpoints(self, embeddings: np.ndarray) -> set[int]:
        """Returns sentence indices AFTER which a new chunk should
        start (index i means: break between sentence i and i+1)."""
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        normalized = embeddings / norms

        similarities = np.sum(normalized[:-1] * normalized[1:], axis=1)
        distances = 1.0 - similarities

        threshold = np.percentile(distances, self.breakpoint_percentile)
        return {i for i, d in enumerate(distances) if d >= threshold}

    @staticmethod
    def _group_sentences(n_sentences: int, breakpoints: set[int]) -> list[list[int]]:
        groups: list[list[int]] = []
        current = [0]
        for i in range(1, n_sentences):
            if (i - 1) in breakpoints:
                groups.append(current)
                current = [i]
            else:
                current.append(i)
        groups.append(current)
        return groups

    def _enforce_size_bounds(
        self, groups: list[list[int]], sentences: list[str]
    ) -> list[list[int]]:
        # Merge undersized groups forward until they hit min_chunk_tokens.
        merged: list[list[int]] = []
        pending: list[int] = []
        for group in groups:
            pending.extend(group)
            token_count = count_tokens(" ".join(sentences[i] for i in pending))
            if token_count >= self.min_chunk_tokens:
                merged.append(pending)
                pending = []
        if pending:
            if merged:
                merged[-1].extend(pending)
            else:
                merged.append(pending)

        # Hard-split anything still oversized at max_chunk_tokens.
        final: list[list[int]] = []
        for group in merged:
            final.extend(self._split_if_oversized(group, sentences))
        return final

    def _split_if_oversized(
        self, group: list[int], sentences: list[str]
    ) -> list[list[int]]:
        text = " ".join(sentences[i] for i in group)
        if count_tokens(text) <= self.max_chunk_tokens:
            return [group]

        pieces: list[list[int]] = []
        current: list[int] = []
        for idx in group:
            current.append(idx)
            piece_text = " ".join(sentences[i] for i in current)
            if count_tokens(piece_text) >= self.max_chunk_tokens:
                pieces.append(current)
                current = []
        if current:
            pieces.append(current)
        return pieces
