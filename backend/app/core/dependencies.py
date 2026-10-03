import threading

from fastapi import HTTPException

from app.pipelines.rag_pipeline import RAGPipeline
from app.pipelines.strategy import ChunkingStrategy, RetrievalStrategy, StrategyConfig

_pipelines: dict[tuple[str, str], RAGPipeline] = {}
_lock = threading.Lock()


def load_pipeline_for(chunking_strategy: ChunkingStrategy, retrieval_strategy: RetrievalStrategy) -> RAGPipeline:
    """Raises FileNotFoundError if that combination's chunks/vector store
    haven't been built. /query/compare catches this per strategy."""
    key = (chunking_strategy, retrieval_strategy)
    with _lock:
        pipeline = _pipelines.get(key)
        if pipeline is None:
            pipeline = RAGPipeline(
                strategy=StrategyConfig(
                    name=f"{chunking_strategy}_{retrieval_strategy}",
                    chunking_strategy=chunking_strategy,
                    retrieval_strategy=retrieval_strategy,
                )
            )
            _pipelines[key] = pipeline
        return pipeline


def loaded_pipelines() -> list[tuple[tuple[str, str], RAGPipeline]]:
    with _lock:
        return list(_pipelines.items())


def clear_pipeline_cache() -> None:
    with _lock:
        _pipelines.clear()


def get_rag_pipeline() -> RAGPipeline:
    """Default pipeline: fixed chunking + vector search."""
    try:
        return load_pipeline_for("fixed", "vector")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def get_pipeline_for_strategy(
    retrieval_strategy: RetrievalStrategy, chunking_strategy: ChunkingStrategy = "fixed"
) -> RAGPipeline:
    """HTTP-facing variant: turns a missing index into a 503."""
    try:
        return load_pipeline_for(chunking_strategy, retrieval_strategy)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc