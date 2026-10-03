import json
import shutil
from typing import Callable

from app.core.config import Settings, get_settings
from app.core.dependencies import clear_pipeline_cache
from app.core.logging import get_logger
from app.embeddings.embedder import get_embedder
from app.ingestion.ingest import run_ingestion, run_semantic_ingestion
from app.ingestion.loaders import discover_pdfs
from app.models.document import Chunk
from app.retrieval.vector_search import VectorStore

logger = get_logger(__name__)

ReportFn = Callable[[float, str], None]
CHUNKING_ORDER = ("fixed", "semantic")


def build_vector_store(chunking: str, settings: Settings) -> int:
    chunks_path = settings.chunks_path_for(chunking)
    with chunks_path.open("r", encoding="utf-8") as f:
        chunks = [Chunk(**d) for d in json.load(f)]
    if not chunks:
        raise ValueError(
            f"No text could be extracted for '{chunking}' chunking. "
            "Scanned/image-only PDFs have no extractable text."
        )
    embedder = get_embedder(settings)
    store = VectorStore()
    store.build(chunks, embedder.embed_texts([c.text for c in chunks]))
    store.save(settings.vector_store_path_for(chunking))
    return len(chunks)


def clear_index(settings: Settings) -> None:
    for chunking in CHUNKING_ORDER:
        settings.chunks_path_for(chunking).unlink(missing_ok=True)
        shutil.rmtree(settings.vector_store_path_for(chunking), ignore_errors=True)


def rebuild_index(report: ReportFn, chunking: list[str] | None = None, settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    selected = [c for c in CHUNKING_ORDER if c in (chunking or CHUNKING_ORDER)]

    try:
        pdfs = discover_pdfs(settings.raw_docs_path)
        if not pdfs:
            clear_index(settings)
            report(1.0, "No documents found — index cleared.")
            return {"documents": 0, "chunks": {}}

        steps = [(kind, c) for c in selected for kind in ("ingest", "embed")]
        chunk_counts: dict[str, int] = {}
        for i, (kind, c) in enumerate(steps):
            verb = "Chunking documents" if kind == "ingest" else "Embedding chunks"
            report(i / len(steps), f"{verb} ({c})…")
            if kind == "ingest":
                runner = run_ingestion if c == "fixed" else run_semantic_ingestion
                runner(settings)
            else:
                chunk_counts[c] = build_vector_store(c, settings)
        report(1.0, "Done.")
        return {"documents": len(pdfs), "chunks": chunk_counts}
    finally:
        clear_pipeline_cache()
