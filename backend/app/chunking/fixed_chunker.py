"""
Strategy A: fixed-size token windows with a fixed overlap. 
This is the baseline every other chunking strategy gets
compared against.
"""
from itertools import groupby

from app.chunking.base import BaseChunker
from app.core.logging import get_logger
from app.ingestion.cleaner import clean_text
from app.ingestion.metadata import extract_year
from app.models.document import Chunk, RawPage
from app.utils.token_counter import decode, encode

logger = get_logger(__name__)


class FixedChunker(BaseChunker):
    strategy_name = "fixed"

    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        if overlap >= chunk_size:
            raise ValueError("overlap must be smaller than chunk_size")
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_pages(self, pages: list[RawPage]) -> list[Chunk]:
        chunks: list[Chunk] = []
        # Pages arrive interleaved across documents; group them back by
        # document_id so each document is chunked independently.
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

        # Concatenate all pages, remembering which page each token
        # roughly falls on so we can still tag chunks with a page number.
        all_tokens: list = []
        token_page_map: list[int] = []
        for page in pages:
            page_tokens = encode(clean_text(page.text))
            all_tokens.extend(page_tokens)
            token_page_map.extend([page.page] * len(page_tokens))

        if not all_tokens:
            return []

        chunks: list[Chunk] = []
        step = self.chunk_size - self.overlap
        chunk_index = 0
        start = 0
        while start < len(all_tokens):
            end = min(start + self.chunk_size, len(all_tokens))
            token_slice = all_tokens[start:end]
            text = decode(token_slice)
            page_for_chunk = token_page_map[start]

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
            chunk_index += 1
            if end == len(all_tokens):
                break
            start += step

        return chunks
