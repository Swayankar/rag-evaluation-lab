import json
from pathlib import Path

from app.chunking.fixed_chunker import FixedChunker
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
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

    _save_chunks(chunks, settings.processed_chunks_path)
    logger.info(
        "Ingestion complete: %d pages -> %d chunks from %d documents",
        len(raw_pages),
        len(chunks),
        len({p.document_id for p in raw_pages}),
    )
    return chunks


def _save_chunks(chunks: list[Chunk], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "fixed_chunks.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump([c.model_dump() for c in chunks], f, indent=2, ensure_ascii=False)
    logger.info("Wrote %s", out_path)
