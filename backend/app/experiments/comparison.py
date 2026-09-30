"""
Compares aggregate metrics across multiple experiments (the output of
EvaluationReport.aggregate(), one per experiment).

The one thing worth getting right here: not every metric is "bigger is
better" — latency and hallucination rate are the opposite. Getting the
direction wrong would silently declare the slowest, most hallucination-
prone strategy the "winner" on those columns.
"""
import json
from dataclasses import dataclass
from pathlib import Path

# "higher" = bigger is better, "lower" = smaller is better. Anything not
# listed defaults to "higher" (see compare()) rather than being dropped,
# so a metric added later doesn't just silently disappear from the table.
METRIC_DIRECTIONS: dict[str, str] = {
    "avg_recall_at_k": "higher",
    "avg_precision_at_k": "higher",
    "avg_mrr": "higher",
    "avg_citation_accuracy": "higher",
    "avg_correctness": "higher",
    "avg_relevance": "higher",
    "avg_completeness": "higher",
    "avg_faithfulness": "higher",
    "hallucination_rate": "lower",
    "avg_latency_ms": "lower",
    "avg_prompt_tokens": "lower",
    "num_errors": "lower",
    "num_judge_errors": "lower",
}

# Metrics that are counts/diagnostics rather than quality scores — shown
# in the per-experiment detail, but excluded from the comparison table and
# the win count, where they'd be misleading (e.g. "fewest errors" isn't a
# meaningful thing to crown a "winner" on the same footing as faithfulness).
_EXCLUDED_FROM_COMPARISON = {"num_questions", "num_errors", "num_judge_errors"}


@dataclass
class ComparisonRow:
    metric: str
    direction: str
    values: dict[str, float]  # experiment_name -> value (only where present)
    best_experiment: str | None


def compare(aggregates: dict[str, dict]) -> list[ComparisonRow]:
    """aggregates: {experiment_name: EvaluationReport.aggregate() dict}."""
    metric_keys: set[str] = set()
    for agg in aggregates.values():
        metric_keys.update(k for k in agg if k not in _EXCLUDED_FROM_COMPARISON)

    rows = []
    for metric in sorted(metric_keys):
        direction = METRIC_DIRECTIONS.get(metric, "higher")
        values = {name: agg[metric] for name, agg in aggregates.items() if metric in agg}
        if not values:
            continue
        best = (max if direction == "higher" else min)(values, key=values.get)
        rows.append(ComparisonRow(metric=metric, direction=direction, values=values, best_experiment=best))
    return rows


def count_wins(rows: list[ComparisonRow]) -> dict[str, int]:
    """How many metrics each experiment came out best on. Not a single
    verdict — an experiment can win on retrieval and lose on latency — but
    a quick way to see which one is winning most often."""
    wins: dict[str, int] = {}
    for row in rows:
        if row.best_experiment:
            wins[row.best_experiment] = wins.get(row.best_experiment, 0) + 1
    return wins


def format_markdown_table(rows: list[ComparisonRow], experiment_names: list[str]) -> str:
    header = "| Metric | " + " | ".join(experiment_names) + " |"
    sep = "|---" + "|---" * len(experiment_names) + "|"
    lines = [header, sep]
    for row in rows:
        cells = []
        for name in experiment_names:
            value = row.values.get(name)
            if value is None:
                cells.append("—")
            else:
                marker = " 🏆" if name == row.best_experiment else ""
                cells.append(f"{value:.3f}{marker}")
        lines.append(f"| {row.metric} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def save_comparison(
    rows: list[ComparisonRow], experiment_names: list[str], skipped: dict[str, str], out_path: Path
) -> None:
    payload = {
        "experiments": experiment_names,
        "skipped": skipped,
        "metrics": [
            {"metric": r.metric, "direction": r.direction, "values": r.values, "best": r.best_experiment}
            for r in rows
        ],
        "wins": count_wins(rows),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)