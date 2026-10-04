import dataclasses
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from app.core.config import Settings
from app.core.dependencies import load_pipeline_for, with_top_k
from app.core.logging import get_logger
from app.evaluation.dataset import EvalDataset
from app.evaluation.runner import EvaluationReport, EvaluationRunner

logger = get_logger(__name__)

ReportFn = Callable[[float, str], None]


def dataset_hash(dataset: EvalDataset) -> str:
    payload = json.dumps([q.model_dump() for q in dataset.questions], sort_keys=True)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:8]


def write_json_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def run_evaluation_job(
    report: ReportFn,
    combos: list[tuple[str, str]],
    top_k: int,
    dataset: EvalDataset,
    settings: Settings,
    run_llm_judges: bool,
) -> dict:
    total = len(combos) * len(dataset)
    done = 0
    ran: list[str] = []
    skipped: dict[str, str] = {}
    d_hash = dataset_hash(dataset)

    for chunking, retrieval in combos:
        name = f"{chunking}_{retrieval}"
        try:
            pipeline = with_top_k(load_pipeline_for(chunking, retrieval), top_k)
        except FileNotFoundError as exc:
            skipped[name] = str(exc)
            done += len(dataset)
            report(done / total, f"Skipped {name} (index not built)")
            continue

        runner = EvaluationRunner(pipeline, run_llm_judges=run_llm_judges)
        eval_report = EvaluationReport(strategy_name=pipeline.strategy.name)
        for i, question in enumerate(dataset.questions, start=1):
            report(done / total, f"{name}: question {i} of {len(dataset)}")
            eval_report.results.append(runner._evaluate_one(question))
            done += 1

        reranker = getattr(pipeline.retriever, "reranker", None)
        write_json_atomic(
            settings.eval_results_dir / f"{pipeline.strategy.name}.json",
            {
                "strategy": pipeline.strategy.name,
                "aggregate": eval_report.aggregate(),
                "results": [dataclasses.asdict(r) for r in eval_report.results],
                "meta": {
                    "ran_at": datetime.now(timezone.utc).isoformat(),
                    "top_k": top_k,
                    "llm_judges": runner.run_llm_judges,
                    "num_questions": len(dataset),
                    "dataset_hash": d_hash,
                    "embedder": type(pipeline.embedder).__name__,
                    "reranker": type(reranker).__name__ if reranker is not None else None,
                    "llm_model": settings.groq_model,
                },
            },
        )
        ran.append(name)

    if not ran:
        raise RuntimeError(
            "No strategy could run: " + "; ".join(f"{k}: {v}" for k, v in skipped.items())
        )
    report(1.0, "Done.")
    return {"ran": ran, "skipped": skipped}
