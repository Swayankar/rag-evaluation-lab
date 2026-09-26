"""
FastAPI dependencies. The default RAG pipeline (plain vector search) is
built once and cached — rebuilding it per-request would mean reloading
the embedding model and vector store every time.
"""
from functools import lru_cache

from fastapi import HTTPException

from app.pipelines.rag_pipeline import RAGPipeline
from app.pipelines.strategy import RetrievalStrategy, StrategyConfig


@lru_cache
def _load_pipeline() -> RAGPipeline:
    return RAGPipeline()


def get_rag_pipeline() -> RAGPipeline:
    try:
        return _load_pipeline()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@lru_cache
def _load_pipeline_for_strategy(retrieval_strategy: RetrievalStrategy) -> RAGPipeline:
    strategy = StrategyConfig(name=f"fixed_{retrieval_strategy}", retrieval_strategy=retrieval_strategy)
    return RAGPipeline(strategy=strategy)


def get_pipeline_for_strategy(retrieval_strategy: RetrievalStrategy) -> RAGPipeline:
    try:
        return _load_pipeline_for_strategy(retrieval_strategy)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
