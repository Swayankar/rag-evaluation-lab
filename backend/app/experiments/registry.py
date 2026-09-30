"""
The 5 canonical experiments:

    Experiment 1: fixed    + vector
    Experiment 2: semantic + vector
    Experiment 3: fixed    + hybrid
    Experiment 4: semantic + hybrid
    Experiment 5: semantic + hybrid_rerank

These are the same chunking_strategy x retrieval_strategy combinations

Each experiment is also a plain JSON file (experiments/experiment_00N.json
at the project root, per the architecture doc's folder layout)
"""
import json
from pathlib import Path

from app.pipelines.strategy import StrategyConfig

CANONICAL_EXPERIMENTS: list[StrategyConfig] = [
    StrategyConfig(name="experiment_1_fixed_vector", chunking_strategy="fixed", retrieval_strategy="vector"),
    StrategyConfig(name="experiment_2_semantic_vector", chunking_strategy="semantic", retrieval_strategy="vector"),
    StrategyConfig(name="experiment_3_fixed_hybrid", chunking_strategy="fixed", retrieval_strategy="hybrid"),
    StrategyConfig(name="experiment_4_semantic_hybrid", chunking_strategy="semantic", retrieval_strategy="hybrid"),
    StrategyConfig(
        name="experiment_5_semantic_hybrid_rerank",
        chunking_strategy="semantic",
        retrieval_strategy="hybrid_rerank",
    ),
]


def _to_dict(cfg: StrategyConfig) -> dict:
    return {
        "name": cfg.name,
        "chunking_strategy": cfg.chunking_strategy,
        "retrieval_strategy": cfg.retrieval_strategy,
        "top_k": cfg.top_k,
    }


def _from_dict(data: dict) -> StrategyConfig:
    return StrategyConfig(
        name=data["name"],
        chunking_strategy=data.get("chunking_strategy", "fixed"),
        retrieval_strategy=data.get("retrieval_strategy", "vector"),
        top_k=data.get("top_k", 5),
    )


def write_canonical_experiment_files(directory: Path) -> list[Path]:
    """Write experiment_001.json..experiment_005.json for the 5 canonical
    experiments. Called once, the first time scripts/compare_experiments.py
    finds an empty experiments/ directory — after that, these files (and
    any you add alongside them) are the source of truth, not this module."""
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, cfg in enumerate(CANONICAL_EXPERIMENTS, start=1):
        path = directory / f"experiment_{i:03d}.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(_to_dict(cfg), f, indent=2)
        paths.append(path)
    return paths


def load_experiment_configs(directory: Path) -> list[StrategyConfig]:
    """Load every experiment_*.json in `directory`, sorted by filename. If
    the directory doesn't exist or has no experiment_*.json files yet,
    falls back to the 5 canonical in-code configs (the caller decides
    whether to also write them out — see write_canonical_experiment_files)."""
    if directory.exists():
        files = sorted(directory.glob("experiment_*.json"))
        if files:
            return [_from_dict(json.loads(f.read_text(encoding="utf-8"))) for f in files]
    return list(CANONICAL_EXPERIMENTS)