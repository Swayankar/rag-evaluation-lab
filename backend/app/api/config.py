import importlib.util
import os

from fastapi import APIRouter, Depends

from app.core.config import Settings
from app.core.dependencies import loaded_pipelines
from app.core.workspaces import workspace_settings

router = APIRouter(prefix="/config", tags=["config"])


@router.get("")
def get_config(settings: Settings = Depends(workspace_settings)) -> dict:
    from app.utils import token_counter

    pipelines = loaded_pipelines(settings.workspace_id)
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
        if settings.server_key_allowed:
            warnings.append("GROQ_API_KEY isn't set — answers and LLM-judge metrics will fail.")
        else:
            warnings.append("No Groq key — paste yours to ask questions or run evaluations.")
    if settings.is_hosted and (os.environ.get("LANGCHAIN_TRACING_V2", "").lower() == "true"):
        warnings.append("LANGCHAIN_TRACING_V2 is set in this server's environment — visitors' prompts and "
                        "document text may be sent to LangSmith. Unset it for a public deployment.")

    return {
        "llm": {
            "provider": "groq",
            "model": settings.groq_model,
            "base_url": settings.groq_base_url,
            "options": settings.model_choices,
            "default_model": settings.default_groq_model or settings.groq_model,
            "model_overridden": settings.model_overridden,
            "custom_allowed": settings.allow_custom_model and (settings.user_supplied_key or not settings.is_hosted),
            "api_key_configured": bool(settings.groq_api_key),
            "key_source": "yours" if settings.user_supplied_key else ("server" if settings.groq_api_key else "none"),
        },
        "workspace": {
            "id": settings.workspace_id,
            "is_sample": settings.is_sample,
            "read_only": settings.workspace_read_only,
            "mode": settings.app_mode,
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
            "langsmith_enabled": settings.langchain_tracing_v2 and bool(settings.langchain_api_key) and not settings.is_hosted,
            "project": settings.langchain_project,
        },
        "loaded_pipelines": [f"{c}_{r}" for (c, r), _ in pipelines],
        "warnings": warnings,
    }