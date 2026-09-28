#!/usr/bin/env python
"""
Smoke test.

Usage:
    cd backend
    python scripts/run_experiment.py
    python scripts/run_experiment.py --chunking semantic --strategy hybrid
    python scripts/run_experiment.py --no-llm-judges   # retrieval/citation metrics only, no Groq calls

Requires:
  - data/evaluation/questions.json (run scripts/create_eval_dataset.py
    first if it doesn't exist yet)
  - Ingestion + vector store already built for the chosen --chunking value
  - GROQ_API_KEY in .env, unless --no-llm-judges is passed (retrieval and
    citation metrics don't need it; answer correctness and faithfulness
    scoring do)

This will:
  1. load the evaluation dataset
  2. run every question through the RAG pipeline for the chosen strategy
  3. score retrieval (Recall@K, Precision@K, MRR), citation accuracy,
     system metrics (latency, approx tokens), and — unless disabled —
     answer quality and faithfulness via an LLM judge
  4. print a summary table and per-question detail
  5. save the full report to data/evaluation/results/<strategy_name>.json
"""
import argparse
import dataclasses
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings  # noqa: E402
from app.core.logging import setup_logging  # noqa: E402
from app.evaluation.dataset import load_eval_dataset  # noqa: E402
from app.evaluation.runner import EvaluationRunner  # noqa: E402
from app.pipelines.rag_pipeline import RAGPipeline  # noqa: E402
from app.pipelines.strategy import StrategyConfig  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the evaluation harness for one strategy")
    parser.add_argument("--chunking", choices=["fixed", "semantic"], default="fixed")
    parser.add_argument(
        "--strategy", choices=["vector", "bm25", "hybrid", "hybrid_rerank"], default="vector"
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--no-llm-judges",
        action="store_true",
        help="Skip answer-correctness/faithfulness scoring (no Groq calls needed)",
    )
    args = parser.parse_args()

    setup_logging()
    settings = get_settings()

    if not settings.eval_dataset_path.exists():
        print(
            f"\nNo evaluation dataset found at {settings.eval_dataset_path}.\n"
            "Run scripts/create_eval_dataset.py first."
        )
        return

    dataset = load_eval_dataset(settings.eval_dataset_path)
    print(f"Loaded {len(dataset)} evaluation question(s).")

    strategy = StrategyConfig(
        name=f"{args.chunking}_{args.strategy}",
        chunking_strategy=args.chunking,
        retrieval_strategy=args.strategy,
        top_k=args.top_k,
    )

    try:
        pipeline = RAGPipeline(settings=settings, strategy=strategy)
    except FileNotFoundError as exc:
        print(f"\n{exc}")
        return

    runner = EvaluationRunner(pipeline, run_llm_judges=not args.no_llm_judges)
    if args.no_llm_judges:
        print("LLM-judge metrics disabled (--no-llm-judges) — scoring retrieval/citation only.")
    elif not runner.run_llm_judges:
        print("LLM-judge metrics disabled automatically (couldn't build a Groq client — check GROQ_API_KEY).")

    print(f"\nRunning strategy: {strategy.name} ...\n")
    report = runner.run(dataset)

    print("Per-question results:")
    for r in report.results:
        print(f"\n[{r.question_id}] {r.question}")
        if r.error:
            print(f"  ❌ generation failed: {r.error}")
            continue
        print(
            f"  retrieval: recall@{args.top_k}={r.retrieval.recall_at_k:.2f} "
            f"precision@{args.top_k}={r.retrieval.precision_at_k:.2f} mrr={r.retrieval.mrr:.2f}"
        )
        if r.citation.num_citations:
            print(f"  citations: {r.citation.num_citations} used, accuracy={r.citation.citation_accuracy:.2f}")
        else:
            print("  citations: none used")
        print(f"  latency: {r.system.latency_ms:.0f}ms  ~{r.system.approx_prompt_tokens} prompt tokens")
        if r.answer_judge:
            j = r.answer_judge
            print(
                f"  answer judge: correctness={j.correctness:.0f} relevance={j.relevance:.0f} "
                f"completeness={j.completeness:.0f}  ({j.rationale})"
            )
        if r.grounding_judge:
            g = r.grounding_judge
            flag = "  ⚠️ possible hallucination" if g.likely_hallucination else ""
            print(f"  grounding judge: faithfulness={g.faithfulness:.0f}{flag}  ({g.rationale})")
        if r.judge_error:
            print(f"  ⚠️  judge error: {r.judge_error}")

    agg = report.aggregate()
    print("\n" + "=" * 60)
    print(f"Aggregate ({strategy.name}, {agg.get('num_questions', 0)} questions):")
    for key, value in agg.items():
        if key == "num_questions":
            continue
        print(f"  {key}: {value:.3f}" if isinstance(value, float) else f"  {key}: {value}")

    out_dir = settings.eval_results_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{strategy.name}.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump({"strategy": strategy.name, "aggregate": agg, "results": [dataclasses.asdict(r) for r in report.results]}, f, indent=2)
    print(f"\nSaved full results to {out_path}")


if __name__ == "__main__":
    main()
