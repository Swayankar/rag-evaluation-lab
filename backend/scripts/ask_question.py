#!/usr/bin/env python

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.logging import setup_logging  # noqa: E402
from app.generation.llm import GroqClientError  # noqa: E402
from app.pipelines.rag_pipeline import RAGPipeline  # noqa: E402


def main() -> None:
    setup_logging()

    if len(sys.argv) < 2:
        print('Usage: python scripts/ask_question.py "your question here"')
        return

    question = " ".join(sys.argv[1:])

    try:
        pipeline = RAGPipeline()
    except FileNotFoundError as exc:
        print(f"\n{exc}")
        return

    print(f"Question: {question}\n")
    print("Retrieving relevant chunks and calling Groq...")

    try:
        result = pipeline.answer(question)
    except GroqClientError as exc:
        print(f"\n❌ {exc}")
        return

    print(f"\nRetrieved {len(result.retrieved_chunks)} chunks:")

    for i, r in enumerate(result.retrieved_chunks, start=1):
        print(
            f"  [{i}] score={r.score:.4f}  "
            f"{r.chunk.document_name} "
            f"(page {r.chunk.page}) — "
            f"{r.chunk.chunk_id}"
        )

    print(f"\nAnswer ({result.latency_ms:.0f}ms):\n{result.answer}")

    if result.citations:
        print("\nCitations the model actually used:")

        for c in result.citations:
            print(
                f"  {c.marker} "
                f"{c.document_name}, "
                f"page {c.page} "
                f"({c.chunk_id})"
            )

    else:
        print(
            "\n⚠️  No bracketed [N] citations found in the answer — the model "
            "may not have followed the citation instruction, or it decided "
            "the context didn't answer the question."
        )


if __name__ == "__main__":
    main()