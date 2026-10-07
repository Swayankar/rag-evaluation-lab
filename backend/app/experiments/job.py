import copy
import dataclasses
from datetime import datetime, timezone
from typing import Callable

from app.core.config import Settings
from app.core.dependencies import load_pipeline_for, prepare_pipeline
from app.core.logging import get_logger
from app.evaluation.dataset import EvalDataset
from app.evaluation.job import dataset_hash, make_runner, write_json_atomic
from app.evaluation.runner import EvaluationReport, EvaluationRunner
from app.experiments.comparison import compare, count_wins
from app.pipelines.rag_pipeline import RAGPipeline
from app.pipelines.strategy import StrategyConfig

logger = get_logger(__name__)

ReportFn = Callable[[float, str], None]


def _pipeline_for(cfg: StrategyConfig, settings: Settings) -> RAGPipeline:
    base = prepare_pipeline(load_pipeline_for(cfg.chunking_strategy, cfg.retrieval_strategy, settings), settings)
    clone = copy.copy(base)
    clone.strategy = dataclasses.replace(base.strategy, name=cfg.name, top_k=cfg.top_k)
    return clone


def run_experiments_job(
    report: ReportFn,
    strategies: list[StrategyConfig],
    dataset: EvalDataset,
    settings: Settings,
    run_llm_judges: bool,
) -> dict:
    total = max(1, len(strategies) * len(dataset))
    done = 0
    d_hash = dataset_hash(dataset)
    results_dir = settings.experiments_results_dir

    aggregates: dict[str, dict] = {}
    skipped: dict[str, str] = {}
    judges_used = run_llm_judges

    for cfg in strategies:
        try:
            pipeline = _pipeline_for(cfg, settings)
        except FileNotFoundError as exc:
            skipped[cfg.name] = str(exc)
            done += len(dataset)
            report(done / total, f"Skipped {cfg.name} (index not built)")
            continue

        runner = make_runner(pipeline, settings, run_llm_judges)
        judges_used = runner.run_llm_judges
        eval_report = EvaluationReport(strategy_name=cfg.name)
        for i, question in enumerate(dataset.questions, start=1):
            report(done / total, f"{cfg.name}: question {i} of {len(dataset)}")
            # _evaluate_one isolates generation/judge failures per question
            eval_report.results.append(runner._evaluate_one(question))
            done += 1

        aggregate = eval_report.aggregate()
        aggregates[cfg.name] = aggregate
        reranker = getattr(pipeline.retriever, "reranker", None)
        write_json_atomic(
            results_dir / f"{cfg.name}.json",
            {
                "strategy": cfg.name,
                "aggregate": aggregate,
                "results": [dataclasses.asdict(r) for r in eval_report.results],
                "meta": {
                    "ran_at": datetime.now(timezone.utc).isoformat(),
                    "chunking_strategy": cfg.chunking_strategy,
                    "retrieval_strategy": cfg.retrieval_strategy,
                    "top_k": cfg.top_k,
                    "llm_judges": runner.run_llm_judges,
                    "num_questions": len(dataset),
                    "dataset_hash": d_hash,
                    "embedder": type(pipeline.embedder).__name__,
                    "reranker": type(reranker).__name__ if reranker is not None else None,
                    "llm_model": settings.groq_model,
                },
            },
        )

    if not aggregates:
        raise RuntimeError(
            "No experiment could run: " + "; ".join(f"{k}: {v}" for k, v in skipped.items())
        )

    rows = compare(aggregates)
    write_json_atomic(
        results_dir / "comparison_latest.json",
        {
            "experiments": list(aggregates),
            "skipped": skipped,
            "metrics": [
                {"metric": r.metric, "direction": r.direction, "values": r.values, "best": r.best_experiment}
                for r in rows
            ],
            "wins": count_wins(rows),
            "meta": {
                "ran_at": datetime.now(timezone.utc).isoformat(),
                "dataset_hash": d_hash,
                "num_questions": len(dataset),
                "llm_judges": judges_used,
                "llm_model": settings.groq_model,
            },
        },
    )
    report(1.0, "Done.")
    return {"ran": list(aggregates), "skipped": skipped}
