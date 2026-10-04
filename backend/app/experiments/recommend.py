COST_METRICS = {"avg_latency_ms", "avg_prompt_tokens"}

_LABELS = {
    "avg_recall_at_k": "recall@K",
    "avg_precision_at_k": "precision@K",
    "avg_mrr": "MRR",
    "avg_citation_accuracy": "citation accuracy",
    "avg_correctness": "correctness",
    "avg_relevance": "relevance",
    "avg_completeness": "completeness",
    "avg_faithfulness": "faithfulness",
    "hallucination_rate": "hallucination rate",
    "avg_latency_ms": "latency",
    "avg_prompt_tokens": "prompt size",
}


def metric_label(metric: str) -> str:
    return _LABELS.get(metric, metric.replace("avg_", "").replace("_", " "))


def _wins_by_experiment(metrics: list[dict], experiments: list[str]) -> dict[str, list[str]]:
    won: dict[str, list[str]] = {name: [] for name in experiments}
    for row in metrics:
        best = row.get("best")
        if best in won:
            won[best].append(row["metric"])
    return won


def _worst_on(metrics: list[dict], name: str) -> list[str]:
    out = []
    for row in metrics:
        values = row.get("values") or {}
        if name not in values or len(values) < 2:
            continue
        pick = min if row.get("direction", "higher") == "higher" else max
        worst = pick(values.values())
        if values[name] == worst and len(set(values.values())) > 1:
            out.append(row["metric"])
    return out


def recommend(comparison: dict | None) -> dict | None:
    """Returns None when there is nothing to recommend from."""
    if not comparison:
        return None
    experiments: list[str] = list(comparison.get("experiments") or [])
    metrics: list[dict] = list(comparison.get("metrics") or [])
    if not experiments or not metrics:
        return None

    won = _wins_by_experiment(metrics, experiments)
    wins = {name: len(ms) for name, ms in won.items()}
    quality_wins = {name: sum(1 for m in ms if m not in COST_METRICS) for name, ms in won.items()}

    latency_row = next((r for r in metrics if r["metric"] == "avg_latency_ms"), None)
    latency = (latency_row or {}).get("values", {})

    def sort_key(name: str):
        return (-wins[name], -quality_wins[name], latency.get(name, float("inf")), name)

    ranked = sorted(experiments, key=sort_key)
    winner = ranked[0]
    top_wins = wins[winner]
    tied = [n for n in ranked if wins[n] == top_wins]
    runner_up = ranked[1] if len(ranked) > 1 else None
    margin = top_wins - wins[runner_up] if runner_up else top_wins

    if runner_up is None:
        confidence = "single"
    elif len(tied) > 1:
        confidence = "tie"
    elif margin >= 3:
        confidence = "clear"
    else:
        confidence = "narrow"

    strengths = won[winner]
    weaknesses = _worst_on(metrics, winner) if runner_up else []

    parts = [f"Best on {top_wins} of {len(metrics)} metrics"]
    if strengths:
        shown = ", ".join(metric_label(m) for m in strengths[:4])
        parts[0] += f" (including {shown})" if len(strengths) > 4 else f" ({shown})"
    if confidence == "tie":
        parts.append(
            f"tied on wins with {', '.join(n for n in tied if n != winner)}; "
            "picked on quality-metric wins, then speed"
        )
    elif confidence == "narrow":
        parts.append(f"only {margin} ahead of {runner_up}")
    elif confidence == "clear":
        parts.append(f"{margin} ahead of {runner_up}")
    if weaknesses:
        parts.append("but weakest on " + ", ".join(metric_label(m) for m in weaknesses[:3]))

    return {
        "name": winner,
        "wins": top_wins,
        "total_metrics": len(metrics),
        "runner_up": {"name": runner_up, "wins": wins[runner_up]} if runner_up else None,
        "margin": margin,
        "confidence": confidence,
        "tied": tied if len(tied) > 1 else [],
        "strengths": strengths,
        "weaknesses": weaknesses,
        "ranking": [{"name": n, "wins": wins[n]} for n in ranked],
        "summary": "; ".join(parts) + ".",
    }
