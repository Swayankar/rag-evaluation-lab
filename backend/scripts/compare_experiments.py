#!/usr/bin/env python
"""
Smoke test.

Usage:
    cd backend
    python scripts/compare_experiments.py
    python scripts/compare_experiments.py --no-llm-judges
    python scripts/compare_experiments.py --experiments-dir ../experiments

Requires:
  - data/evaluation/questions.json (scripts/create_eval_dataset.py)
  - For each experiment you want to actually run (not skip): ingestion +
    vector store already built for that experiment's chunking strategy.
    An experiment using semantic chunking needs
    `ingest_documents.py --chunking semantic` and
    `build_vector_store.py --chunking semantic` run first.
    fixed-chunking experiments only need the defaults.
  - GROQ_API_KEY, unless --no-llm-judges is passed

On first run, this writes the 5 canonical experiments from the
architecture doc to <experiments-dir>/experiment_001.json..005.json (by
default, ../experiments relative to backend/ — the project-root
experiments/ folder) so you can review or edit them afterward. If that
directory already has experiment_*.json files, those are used instead —
add, remove, or edit them to run your own set.

This will:
  1. run every experiment configuration against the same questions
  2. skip (not crash on) any experiment whose prerequisites aren't built
     yet, with a clear message about which command to run
  3. print a metric-by-metric comparison table across everything that DID
     run, with the best value on each metric marked
  4. save the comparison + full per-experiment detail to
     <experiments-dir>/results/

To also get these into LangSmith for the same comparison in its UI, run
scripts/run_experiment.py --langsmith once per chunking/strategy
combination — that reuses the exact same evaluators, so the
two comparisons will agree.
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
from app.experiments.comparison import (  # noqa: E402
    compare,
    count_wins,
    format_markdown_table,
    save_comparison,
)
from app.experiments.experiment_runner import ExperimentBatchRunner  # noqa: E402
from app.experiments.registry import load_experiment_configs, write_canonical_experiment_files  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run and compare every experiment configuration")
    parser.add_argument(
        "--experiments-dir",
        default=None,
        help="Directory of experiment_*.json files (default: ../experiments, the project root)",
    )
    parser.add_argument(
        "--no-llm-judges",
        action="store_true",
        help="Skip answer-correctness/faithfulness scoring for every experiment (no extra Groq calls)",
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

    experiments_dir = Path(args.experiments_dir) if args.experiments_dir else Path("../experiments")
    if not experiments_dir.exists() or not any(experiments_dir.glob("experiment_*.json")):
        written = write_canonical_experiment_files(experiments_dir)
        print(f"Wrote {len(written)} canonical experiment configs to {experiments_dir}/ (edit them to customize).")
    strategies = load_experiment_configs(experiments_dir)
    print(f"Running {len(strategies)} experiment(s): {', '.join(s.name for s in strategies)}\n")

    runner = ExperimentBatchRunner(settings=settings, run_llm_judges=not args.no_llm_judges)
    batch = runner.run(strategies, dataset)

    skipped = batch.skipped()
    skipped_map = {r.strategy.name: r.setup_error for r in skipped}
    if skipped:
        print("Skipped (prerequisites not built yet):")
        for r in skipped:
            print(f"  {r.strategy.name}: {r.setup_error}")
        print()

    successful = batch.successful()
    if not successful:
        print("No experiments could be run — build prerequisites first (see the messages above).")
        return

    aggregates = batch.aggregates()
    experiment_names = [r.strategy.name for r in successful]
    rows = compare(aggregates)

    print(format_markdown_table(rows, experiment_names))

    wins = count_wins(rows)
    if wins:
        print("\nWin count (best value on how many metrics — not a single verdict):")
        for name, count in sorted(wins.items(), key=lambda kv: -kv[1]):
            print(f"  {name}: {count}")

    out_dir = experiments_dir / "results"
    comparison_path = out_dir / "comparison_latest.json"
    save_comparison(rows, experiment_names, skipped_map, comparison_path)
    print(f"\nSaved comparison to {comparison_path}")

    for r in successful:
        detail_path = out_dir / f"{r.strategy.name}.json"
        with detail_path.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "strategy": r.strategy.name,
                    "aggregate": aggregates[r.strategy.name],
                    "results": [dataclasses.asdict(qr) for qr in r.report.results],
                },
                f,
                indent=2,
            )
    print(f"Saved per-experiment detail to {out_dir}/")


if __name__ == "__main__":
    main()