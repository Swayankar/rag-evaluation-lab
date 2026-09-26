"""
Describes which chunking + retrieval combination a pipeline run uses.
Together, chunking_strategy x retrieval_strategy map directly onto the
5 experiments:

    Experiment 1: fixed    + vector
    Experiment 2: semantic + vector
    Experiment 3: fixed    + hybrid
    Experiment 4: semantic + hybrid
    Experiment 5: semantic + hybrid_rerank

The experiments framework will run all five and compare them;
for now this is the single seam both scripts/ask_question.py and the
/query API use to pick a combination for one question at a time.
"""
from dataclasses import dataclass
from typing import Literal

ChunkingStrategy = Literal["fixed", "semantic"]
RetrievalStrategy = Literal["vector", "bm25", "hybrid", "hybrid_rerank"]

_VALID_CHUNKING_STRATEGIES = {"fixed", "semantic"}
_VALID_RETRIEVAL_STRATEGIES = {"vector", "bm25", "hybrid", "hybrid_rerank"}


@dataclass
class StrategyConfig:
    name: str = "fixed_vector"
    chunking_strategy: ChunkingStrategy = "fixed"
    retrieval_strategy: RetrievalStrategy = "vector"
    top_k: int = 5

    def __post_init__(self) -> None:
        if self.chunking_strategy not in _VALID_CHUNKING_STRATEGIES:
            raise ValueError(
                f"Unknown chunking_strategy {self.chunking_strategy!r}; "
                f"expected one of {sorted(_VALID_CHUNKING_STRATEGIES)}"
            )
        if self.retrieval_strategy not in _VALID_RETRIEVAL_STRATEGIES:
            raise ValueError(
                f"Unknown retrieval_strategy {self.retrieval_strategy!r}; "
                f"expected one of {sorted(_VALID_RETRIEVAL_STRATEGIES)}"
            )
