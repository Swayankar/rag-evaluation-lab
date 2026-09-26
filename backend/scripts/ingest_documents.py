#!/usr/bin/env python
"""
Smoke test.

Usage:
    cd backend
    python scripts/ingest_documents.py
    python scripts/ingest_documents.py --chunking semantic
    python scripts/ingest_documents.py --chunking both

Drop your PDFs into data/documents/<department>/*.pdf first (department
folder name becomes the `department` field — e.g. hr, finance, legal, it).

--chunking fixed (default) is same as its original behavior:
    writes data/processed/chunks/fixed_chunks.json
--chunking semantic runs Strategy B (embedding-similarity topic
breaks) instead:
    writes data/processed/chunks/semantic_chunks.json
--chunking both runs both and prints a side-by-side comparison —
chunk counts and average chunk length per document — so you can see how
the two strategies actually differ on your real corpus.

This will:
  1. find every PDF under data/documents/
  2. extract + clean the text
  3. run the chosen chunker(s) over it
  4. write the corresponding chunks JSON file(s)
  5. print a summary + a couple of sample chunks so you can eyeball the output
"""
import argparse
import sys
from pathlib import Path

# Allow running this script directly (python scripts/ingest_documents.py)
# without having to `pip install -e .` first.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.logging import setup_logging  # noqa: E402
from app.ingestion.ingest import run_ingestion, run_semantic_ingestion  # noqa: E402
from app.models.document import Chunk  # noqa: E402
from app.utils.token_counter import count_tokens  # noqa: E402


def _print_summary(label: str, chunks: list[Chunk]) -> None:
    if not chunks:
        print(f"\n[{label}] No chunks were produced.")
        return

    avg_tokens = sum(count_tokens(c.text) for c in chunks) / len(chunks)
    doc_count = len({c.document_id for c in chunks})
    print(f"\n✅ [{label}] {len(chunks)} chunks from {doc_count} documents (avg {avg_tokens:.0f} tokens/chunk)")
    print("Sample chunks:")
    for chunk in chunks[:3]:
        print("-" * 70)
        print(f"chunk_id:   {chunk.chunk_id}")
        print(f"document:   {chunk.document_name} ({chunk.department}, year={chunk.year})")
        print(f"page:       {chunk.page}")
        print(f"tokens:     ~{count_tokens(chunk.text)}")
        print(f"text[:200]: {chunk.text[:200]!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest PDFs into chunks")
    parser.add_argument(
        "--chunking",
        choices=["fixed", "semantic", "both"],
        default="fixed",
        help="Which chunking strategy to run (default: fixed)",
    )
    args = parser.parse_args()

    setup_logging()

    if args.chunking in ("fixed", "both"):
        fixed_chunks = run_ingestion()
        _print_summary("fixed", fixed_chunks)
        if not fixed_chunks:
            print(
                "\nMake sure your PDFs are under "
                "backend/data/documents/<department>/*.pdf"
            )

    if args.chunking in ("semantic", "both"):
        semantic_chunks = run_semantic_ingestion()
        _print_summary("semantic", semantic_chunks)
        if not semantic_chunks:
            print(
                "\nMake sure your PDFs are under "
                "backend/data/documents/<department>/*.pdf"
            )

    if args.chunking == "both":
        print(
            "\nBoth chunk files are saved side by side — "
            "data/processed/chunks/fixed_chunks.json and "
            "data/processed/chunks/semantic_chunks.json. "
            "Compare the chunk counts/avg lengths above, or open both "
            "files to see how differently they split the same documents."
        )


if __name__ == "__main__":
    main()