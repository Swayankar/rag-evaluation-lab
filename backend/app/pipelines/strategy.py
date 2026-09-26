"""
Describes which chunking + retrieval combination a pipeline run uses.
"""
from dataclasses import dataclass
from typing import Literal

RetrievalStrategy = Literal["vector", "bm25", "hybrid", "hybrid_rerank"]


@dataclass
class StrategyConfig:
    name: str = "fixed_vector"
    chunking_strategy: str = "fixed"
    retrieval_strategy: RetrievalStrategy = "vector"
    top_k: int = 5

    def __post_init__(self) -> None:
        valid = {"vector", "bm25", "hybrid", "hybrid_rerank"}
        if self.retrieval_strategy not in valid:
            raise ValueError(
                f"Unknown retrieval_strategy {self.retrieval_strategy!r}; expected one of {sorted(valid)}"
            )
