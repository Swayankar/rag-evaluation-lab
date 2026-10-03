"""
FastAPI dependencies. Pipelines are built once per (chunking, retrieval)
combination and cached — rebuilding one per request would mean reloading the
embedding model, vector store and (for hybrid_rerank) the cross-encoder every time.
"""
from functools import lru_cache

from fastapi import HTTPException

from app.pipelines.rag_pipeline import RAGPipeline
from app.pipelines.strategy import ChunkingStrategy, RetrievalStrategy, StrategyConfig


@lru_cache
def _load_pipeline() -> RAGPipeline:
    return RAGPipeline()


def get_rag_pipeline() -> RAGPipeline:
    """Default pipeline: fixed chunking + vector search."""
    try:
        return _load_pipeline()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@lru_cache(maxsize=16)
def _load_pipeline_for(chunking_strategy: ChunkingStrategy, retrieval_strategy: RetrievalStrategy) -> RAGPipeline:
    strategy = StrategyConfig(
        name=f"{chunking_strategy}_{retrieval_strategy}",
        chunking_strategy=chunking_strategy,
        retrieval_strategy=retrieval_strategy,
    )
    return RAGPipeline(strategy=strategy)


def load_pipeline_for(chunking_strategy: ChunkingStrategy, retrieval_strategy: RetrievalStrategy) -> RAGPipeline:
    """Raises FileNotFoundError if that combination's chunks/vector store
    haven't been built. /query/compare catches this per strategy."""
    return _load_pipeline_for(chunking_strategy, retrieval_strategy)


def get_pipeline_for_strategy(
    retrieval_strategy: RetrievalStrategy, chunking_strategy: ChunkingStrategy = "fixed"
) -> RAGPipeline:
    """HTTP-facing variant: turns a missing index into a 503."""
    try:
        return load_pipeline_for(chunking_strategy, retrieval_strategy)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
