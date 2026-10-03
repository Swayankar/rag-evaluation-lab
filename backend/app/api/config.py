import importlib.util

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.core.dependencies import loaded_pipelines

router = APIRouter(prefix="/config", tags=["config"])


@router.get("")
def get_config(settings: Settings = Depends(get_settings)) -> dict:
    from app.utils import token_counter

    pipelines = loaded_pipelines()
    embedders = sorted({type(p.embedder).__name__ for _, p in pipelines})
    rerankers = sorted(
        {type(r).__name__ for _, p in pipelines if (r := getattr(p.retriever, "reranker", None)) is not None}
    )
    tokenizer = "whitespace (approximate)" if type(token_counter._ENCODING).__name__ == "_WhitespaceEncoding" else "tiktoken"
    st_installed = importlib.util.find_spec("sentence_transformers") is not None

    warnings: list[str] = []
    if "HashingEmbedder" in embedders:
        warnings.append("A pipeline is using the HashingEmbedder fallback — scores are NOT real semantic retrieval quality.")
    elif settings.embedding_backend == "hashing":
        warnings.append("embedding_backend is set to 'hashing' — retrieval is not semantic.")
    elif not st_installed:
        warnings.append("sentence-transformers isn't installed — the hashing fallback will be used.")
    if "NoOpReranker" in rerankers:
        warnings.append("The cross-encoder couldn't load — hybrid_rerank is behaving like plain hybrid.")
    if tokenizer != "tiktoken":
        warnings.append("tiktoken unavailable — chunk sizes and token counts are approximate.")
    if not settings.groq_api_key:
        warnings.append("GROQ_API_KEY isn't set — answers and LLM-judge metrics will fail.")

    return {
        "llm": {
            "provider": "groq",
            "model": settings.groq_model,
            "base_url": settings.groq_base_url,
            "api_key_configured": bool(settings.groq_api_key),
        },
        "embeddings": {
            "configured_backend": settings.embedding_backend,
            "model_name": settings.embedding_model_name,
            "sentence_transformers_installed": st_installed,
            "active": embedders,
        },
        "reranker": {"active": rerankers},
        "tokenizer": tokenizer,
        "chunking": {
            "fixed_chunk_size": settings.fixed_chunk_size,
            "fixed_chunk_overlap": settings.fixed_chunk_overlap,
            "semantic_breakpoint_percentile": settings.semantic_breakpoint_percentile,
            "semantic_min_chunk_tokens": settings.semantic_min_chunk_tokens,
            "semantic_max_chunk_tokens": settings.semantic_max_chunk_tokens,
        },
        "tracing": {
            "langsmith_enabled": settings.langchain_tracing_v2 and bool(settings.langchain_api_key),
            "project": settings.langchain_project,
        },
        "loaded_pipelines": [f"{c}_{r}" for (c, r), _ in pipelines],
        "warnings": warnings,
    }