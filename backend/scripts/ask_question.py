#!/usr/bin/env python
"""
Smoke test.

Usage:
    cd backend
    python scripts/ask_question.py "How many weeks of parental leave do employees get?"
    python scripts/ask_question.py "How many weeks of parental leave?" --strategy hybrid
    python scripts/ask_question.py "How many weeks of parental leave?" --strategy hybrid_rerank --top-k 8

--strategy chooses which retrieval strategy answers the question:
    vector         Experiment: plain vector (semantic) search
    bm25           lexical keyword search — good for exact terms/numbers
    hybrid         Experiment: vector + BM25, combined via Reciprocal Rank Fusion
    hybrid_rerank  Experiment: hybrid, then reranked with a cross-encoder

Requires:
  - (data/processed/chunks + data/processed/vector_store exist)
  - GROQ_API_KEY set in the .env file at the project root

This will:
  1. retrieve the top-K matching chunks using the chosen strategy
  2. build a prompt from them and call the Groq API
  3. print the answer, its citations, and which chunks were actually retrieved
     (so you can see the full chain: retrieval -> prompt -> answer)
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.logging import setup_logging  # noqa: E402
from app.generation.llm import GroqClientError  # noqa: E402
from app.pipelines.rag_pipeline import RAGPipeline  # noqa: E402
from app.pipelines.strategy import StrategyConfig  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask a question through the RAG pipeline")
    parser.add_argument("question", help="The question to ask")
    parser.add_argument(
        "--strategy",
        choices=["vector", "bm25", "hybrid", "hybrid_rerank"],
        default="vector",
        help="Retrieval strategy to use (default: vector)",
    )
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    setup_logging()

    strategy = StrategyConfig(
        name=f"fixed_{args.strategy}",
        retrieval_strategy=args.strategy,
        top_k=args.top_k,
    )

    try:
        pipeline = RAGPipeline(strategy=strategy)
    except FileNotFoundError as exc:
        print(f"\n{exc}")
        return

    print(f"Question: {args.question}")
    print(f"Strategy: {args.strategy}\n")
    print("Retrieving relevant chunks and calling Groq...")

    try:
        result = pipeline.answer(args.question)
    except GroqClientError as exc:
        print(f"\n❌ {exc}")
        return

    print(f"\nRetrieved {len(result.retrieved_chunks)} chunks:")
    for i, r in enumerate(result.retrieved_chunks, start=1):
        print(f"  [{i}] score={r.score:.4f}  {r.chunk.document_name} (page {r.chunk.page}) — {r.chunk.chunk_id}")

    print(f"\nAnswer ({result.latency_ms:.0f}ms):\n{result.answer}")

    if result.citations:
        print("\nCitations the model actually used:")
        for c in result.citations:
            print(f"  {c.marker} {c.document_name}, page {c.page} ({c.chunk_id})")
    else:
        print(
            "\n⚠️  No bracketed [N] citations found in the answer — the model "
            "may not have followed the citation instruction, or it decided "
            "the context didn't answer the question."
        )


if __name__ == "__main__":
    main()
