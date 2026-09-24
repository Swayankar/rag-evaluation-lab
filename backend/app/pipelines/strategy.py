"""
Describes which chunking + retrieval combination a pipeline run uses.
Now it only has one real option (fixed chunking + vector search)
"""
from dataclasses import dataclass


@dataclass
class StrategyConfig:
    name: str = "fixed_vector"
    chunking_strategy: str = "fixed"
    retrieval_strategy: str = "vector"
    top_k: int = 5
