#!/usr/bin/env python

import sys
from pathlib import Path

# Allow running this script directly (python scripts/ingest_documents.py)
# without having to `pip install -e .` first.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.logging import setup_logging  # noqa: E402
from app.ingestion.ingest import run_ingestion  # noqa: E402


def main() -> None:
    setup_logging()
    chunks = run_ingestion()

    if not chunks:
        print(
            "\nNo chunks were produced. Make sure your PDFs are under "
            "backend/data/documents/<department>/*.pdf"
        )
        return

    print(f"\n✅ Produced {len(chunks)} chunks.\n")
    print("Sample chunks:")
    for chunk in chunks[:3]:
        print("-" * 70)
        print(f"chunk_id:   {chunk.chunk_id}")
        print(f"document:   {chunk.document_name} ({chunk.department}, year={chunk.year})")
        print(f"page:       {chunk.page}")
        print(f"text[:200]: {chunk.text[:200]!r}")


if __name__ == "__main__":
    main()
