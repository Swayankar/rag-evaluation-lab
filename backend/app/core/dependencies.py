"""
FastAPI dependencies. Right now this is just the RAG pipeline, built
once and reused across requests - rebuilding it per-request would mean
reloading the embedding model and vector store every time.
"""
from functools import lru_cache

from fastapi import HTTPException

from app.pipelines.rag_pipeline import RAGPipeline


@lru_cache
def _load_pipeline() -> RAGPipeline:
    return RAGPipeline()


def get_rag_pipeline() -> RAGPipeline:
    try:
        return _load_pipeline()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
