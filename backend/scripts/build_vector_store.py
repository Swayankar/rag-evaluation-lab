#!/usr/bin/env python
"""
Smoke test.

Usage:
    cd backend
    python scripts/build_vector_store.py
    python scripts/build_vector_store.py --chunking semantic
    python scripts/build_vector_store.py --query "How many weeks of parental leave do employees get?"

--chunking fixed (default) reads data/processed/chunks/fixed_chunks.json
and writes data/processed/vector_store/.
--chunking semantic reads data/processed/chunks/semantic_chunks.json
(run scripts/ingest_documents.py --chunking semantic first) and writes
to a sibling directory, data/processed/vector_store_semantic/, so both
can exist and be compared side by side.

This will:
  1. load the chunks produced by ingestion for the chosen strategy
  2. embed every chunk's text
  3. build + save a vector store
  4. run a sanity check: query with one chunk's own text and confirm
     it retrieves itself as the top (or near-top) match
  5. if --query is given, run that as a real retrieval test and print
     the top matches with their source document/page
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings  # noqa: E402
from app.core.logging import get_logger, setup_logging  # noqa: E402
from app.embeddings.embedder import get_embedder  # noqa: E402
from app.models.document import Chunk  # noqa: E402
from app.retrieval.vector_search import VectorStore  # noqa: E402


logger = get_logger(__name__)


def load_chunks(path: Path) -> list[Chunk]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return [Chunk(**d) for d in data]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build + test the vector store")
    parser.add_argument(
        "--chunking",
        choices=["fixed", "semantic"],
        default="fixed",
        help="Which chunking strategy's output to embed (default: fixed)",
    )
    parser.add_argument("--query", default=None, help="A real question to test retrieval with")
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    setup_logging()
    settings = get_settings()

    chunks_path = settings.chunks_path_for(args.chunking)
    if not chunks_path.exists():
        ingest_flag = "" if args.chunking == "fixed" else f" --chunking {args.chunking}"
        print(
            f"\nNo chunks found at {chunks_path}.\n"
            f"Run ingestion first: python scripts/ingest_documents.py{ingest_flag}"
        )
        return

    chunks = load_chunks(chunks_path)
    print(f"Loaded {len(chunks)} '{args.chunking}' chunks.")

    embedder = get_embedder(settings)
    print(f"Embedder: {type(embedder).__name__} (dim={embedder.dimension})")

    texts = [c.text for c in chunks]
    embeddings = embedder.embed_texts(texts)

    store = VectorStore()
    store.build(chunks, embeddings)
    vector_store_path = settings.vector_store_path_for(args.chunking)
    store.save(vector_store_path)
    print(
        f"\n✅ Vector store saved to {vector_store_path} "
        f"({len(store)} vectors, dim={embeddings.shape[1]})"
    )

    # Sanity check: a chunk's own text should retrieve itself (or rank very
    # highly) — this catches wiring bugs (mismatched ordering, bad
    # normalization, etc.) independent of embedding quality.
    sample = chunks[0]
    results = store.search(embedder.embed_query(sample.text), top_k=args.top_k)
    print("\nSelf-retrieval sanity check (querying with chunk 0's own text):")
    for chunk, score in results:
        marker = "  <-- itself" if chunk.chunk_id == sample.chunk_id else ""
        print(f"  {score:.4f}  {chunk.chunk_id}{marker}")
    top_match_is_itself = bool(results) and results[0][0].chunk_id == sample.chunk_id
    if top_match_is_itself:
        print("  ✅ Top match is the chunk itself — wiring looks correct.")
    else:
        print(
            "  ⚠️  Top match wasn't the chunk itself — worth a look "
            "(can happen with near-duplicate chunks or the hashing fallback on a tiny corpus)."
        )

    if args.query:
        results = store.search(embedder.embed_query(args.query), top_k=args.top_k)
        print(f"\nResults for your query: {args.query!r}")
        for chunk, score in results:
            print(f"  {score:.4f}  {chunk.chunk_id}  ({chunk.document_name}, page {chunk.page})")
            print(f"           {chunk.text[:150]!r}")


if __name__ == "__main__":
    main()