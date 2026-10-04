import time

from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import (
    get_pipeline_for_strategy,
    get_rag_pipeline,
    load_pipeline_for,
    with_top_k as _with_top_k,
)
from app.core.logging import get_logger
from app.generation.llm import GroqClientError
from app.models.query import QueryResult
from app.models.schemas import (
    CitationResponse,
    CompareItem,
    CompareRequest,
    CompareResponse,
    QueryRequest,
    QueryResponse,
    RetrievedChunkResponse,
)
from app.pipelines.rag_pipeline import RAGPipeline

logger = get_logger(__name__)

router = APIRouter(prefix="/query", tags=["query"])

CHUNKING_OPTIONS = ("fixed", "semantic")
RETRIEVAL_OPTIONS = ("vector", "bm25", "hybrid", "hybrid_rerank")
ALL_COMBINATIONS = [(c, r) for c in CHUNKING_OPTIONS for r in RETRIEVAL_OPTIONS]


def _to_response(result: QueryResult, pipeline: RAGPipeline) -> QueryResponse:
    return QueryResponse(
        question=result.question,
        answer=result.answer,
        citations=[CitationResponse(**c.model_dump()) for c in result.citations],
        retrieved_chunks=[
            RetrievedChunkResponse(
                chunk_id=r.chunk.chunk_id,
                document_name=r.chunk.document_name,
                department=r.chunk.department,
                page=r.chunk.page,
                score=r.score,
                text=r.chunk.text,
            )
            for r in result.retrieved_chunks
        ],
        strategy=result.strategy,
        latency_ms=result.latency_ms,
        chunking_strategy=pipeline.strategy.chunking_strategy,
        retrieval_strategy=pipeline.strategy.retrieval_strategy,
    )


@router.post("", response_model=QueryResponse)
def ask_question(
    request: QueryRequest,
    pipeline: RAGPipeline = Depends(get_rag_pipeline),
) -> QueryResponse:
    chunking = request.chunking_strategy or "fixed"
    retrieval = request.retrieval_strategy or "vector"
    if (chunking, retrieval) != ("fixed", "vector"):
        pipeline = get_pipeline_for_strategy(retrieval, chunking)

    pipeline = _with_top_k(pipeline, request.top_k)

    try:
        result = pipeline.answer(request.question)
    except GroqClientError as exc:
        logger.error("Groq call failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return _to_response(result, pipeline)


@router.post("/compare", response_model=CompareResponse)
def compare_strategies(request: CompareRequest) -> CompareResponse:
    """Run one question through several chunking x retrieval combinations.

    Runs sequentially (Groq's free tier rate-limits parallel calls). Failures
    are isolated per strategy: an unbuilt index or a failed LLM call becomes
    that strategy's `error`, and the others still run."""
    if request.strategies:
        combos = [(s.chunking_strategy, s.retrieval_strategy) for s in request.strategies]
    else:
        combos = list(ALL_COMBINATIONS)
    combos = list(dict.fromkeys(combos))

    start = time.perf_counter()
    items: list[CompareItem] = []
    for chunking, retrieval in combos:
        name = f"{chunking}_{retrieval}"
        base = dict(strategy_name=name, chunking_strategy=chunking, retrieval_strategy=retrieval)
        try:
            pipeline = _with_top_k(load_pipeline_for(chunking, retrieval), request.top_k)
        except FileNotFoundError as exc:
            items.append(CompareItem(**base, error=str(exc)))
            continue

        try:
            result = pipeline.answer(request.question)
        except GroqClientError as exc:
            logger.error("Groq call failed for %s: %s", name, exc)
            items.append(CompareItem(**base, error=str(exc)))
            continue
        except Exception as exc:
            logger.exception("Strategy %s failed", name)
            items.append(CompareItem(**base, error=f"{type(exc).__name__}: {exc}"))
            continue

        items.append(CompareItem(**base, result=_to_response(result, pipeline)))

    return CompareResponse(
        question=request.question,
        results=items,
        total_latency_ms=(time.perf_counter() - start) * 1000,
    )
