"""
Runs ingestion for one chunking strategy at a time:

    PDF -> extract text -> clean -> chunk -> save JSON

run_ingestion() is the original path (fixed chunking) and is
untouched — same signature, same output file (fixed_chunks.json).
run_semantic_ingestion() is addition: same PDF-loading and
cleaning, but chunked with SemanticChunker and saved to a sibling file
(semantic_chunks.json) so both can be compared side by side without
either overwriting the other.

This intentionally stops before embeddings/vector storage
(and, for semantic chunks, scripts/build_vector_store.py
--chunking semantic).
"""
import json
from pathlib import Path

from app.chunking.fixed_chunker import FixedChunker
from app.chunking.semantic_chunker import SemanticChunker
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.embeddings.embedder import get_embedder
from app.ingestion.cleaner import clean_text
from app.ingestion.loaders import load_all_pdfs
from app.models.document import Chunk

logger = get_logger(__name__)


def run_ingestion(settings: Settings | None = None) -> list[Chunk]:
    settings = settings or get_settings()

    raw_pages = load_all_pdfs(settings.raw_docs_path)
    for page in raw_pages:
        page.text = clean_text(page.text)

    chunker = FixedChunker(
        chunk_size=settings.fixed_chunk_size,
        overlap=settings.fixed_chunk_overlap,
    )
    chunks = chunker.chunk_pages(raw_pages)

    _save_chunks(chunks, settings.chunks_path_for("fixed"))
    logger.info(
        "Fixed chunking complete: %d pages -> %d chunks from %d documents",
        len(raw_pages),
        len(chunks),
        len({p.document_id for p in raw_pages}),
    )
    return chunks


def run_semantic_ingestion(settings: Settings | None = None) -> list[Chunk]:
    settings = settings or get_settings()

    raw_pages = load_all_pdfs(settings.raw_docs_path)
    for page in raw_pages:
        page.text = clean_text(page.text)

    embedder = get_embedder(settings)
    chunker = SemanticChunker(
        embedder=embedder,
        settings=settings,
        breakpoint_percentile=settings.semantic_breakpoint_percentile,
        min_chunk_tokens=settings.semantic_min_chunk_tokens,
        max_chunk_tokens=settings.semantic_max_chunk_tokens,
    )
    chunks = chunker.chunk_pages(raw_pages)

    _save_chunks(chunks, settings.chunks_path_for("semantic"))
    logger.info(
        "Semantic chunking complete: %d pages -> %d chunks from %d documents",
        len(raw_pages),
        len(chunks),
        len({p.document_id for p in raw_pages}),
    )
    return chunks


def _save_chunks(chunks: list[Chunk], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump([c.model_dump() for c in chunks], f, indent=2, ensure_ascii=False)
    logger.info("Wrote %s", out_path)