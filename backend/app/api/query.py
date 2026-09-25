from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_rag_pipeline
from app.core.logging import get_logger
from app.generation.llm import GroqClientError
from app.models.schemas import (
    CitationResponse,
    QueryRequest,
    QueryResponse,
    RetrievedChunkResponse,
)
from app.pipelines.rag_pipeline import RAGPipeline

logger = get_logger(__name__)

router = APIRouter(prefix="/query", tags=["query"])


@router.post("", response_model=QueryResponse)
def ask_question(
    request: QueryRequest,
    pipeline: RAGPipeline = Depends(get_rag_pipeline),
) -> QueryResponse:
    if request.top_k is not None:
        pipeline.strategy.top_k = request.top_k

    try:
        result = pipeline.answer(request.question)
    except GroqClientError as exc:
        logger.error("Grok call failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

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
    )
