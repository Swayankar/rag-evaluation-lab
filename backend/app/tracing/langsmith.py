"""
LangSmith tracing support.

Design goals:
  - Opt-in and off by default. Nothing is sent anywhere unless
    LANGCHAIN_TRACING_V2=true AND LANGCHAIN_API_KEY is set in .env.
  - Never break the app. If langsmith isn't importable, `traceable` becomes
    a no-op decorator, and every helper here silently does nothing when
    tracing is off — same graceful-degradation pattern as the embedding,
    tokenizer, and reranker fallbacks elsewhere in this project.

One gotcha this module exists to solve: pydantic-settings reads .env into
the Settings object, but the LangSmith SDK reads its configuration from
*os.environ* — so without configure_tracing() copying the values across,
setting LANGCHAIN_TRACING_V2=true in .env would silently do nothing.
"""
import os
from typing import Any, Callable

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

try:
    from langsmith import traceable as _langsmith_traceable

    LANGSMITH_AVAILABLE = True
except ImportError:  # pragma: no cover - only hit if langsmith is missing
    _langsmith_traceable = None
    LANGSMITH_AVAILABLE = False


def traceable(*args: Any, **kwargs: Any) -> Callable:
    """Drop-in for langsmith.traceable that degrades to a no-op decorator
    when langsmith isn't installed. Supports both @traceable and
    @traceable(...) call styles."""
    if LANGSMITH_AVAILABLE:
        return _langsmith_traceable(*args, **kwargs)

    if len(args) == 1 and callable(args[0]) and not kwargs:
        return args[0]

    def decorator(func: Callable) -> Callable:
        return func

    return decorator


def configure_tracing(settings: Settings, force: bool = False) -> bool:
    if not (settings.langchain_tracing_v2 or force):
        return False

    if not LANGSMITH_AVAILABLE:
        logger.warning("Tracing requested but the `langsmith` package isn't installed — tracing disabled.")
        return False

    if not settings.langchain_api_key:
        if not force:  # with force, the caller reports the missing key itself
            logger.warning(
                "LANGCHAIN_TRACING_V2=true but LANGCHAIN_API_KEY is empty — tracing disabled."
            )
        return False

    # Set both the current (LANGSMITH_*) and legacy (LANGCHAIN_*) names so this
    # works across SDK versions.
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGSMITH_API_KEY"] = settings.langchain_api_key
    os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
    os.environ["LANGSMITH_PROJECT"] = settings.langchain_project
    os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
    if settings.langsmith_endpoint:
        os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
        os.environ["LANGCHAIN_ENDPOINT"] = settings.langsmith_endpoint

    _clear_langsmith_env_cache()
    return True


def _clear_langsmith_env_cache() -> None:
    """The SDK caches environment lookups, so values set after its first
    read would otherwise be ignored."""
    try:
        from langsmith import utils

        utils.get_env_var.cache_clear()
    except Exception:  # noqa: BLE001 - best effort; older SDKs may not cache
        pass


def tracing_enabled() -> bool:
    if not LANGSMITH_AVAILABLE:
        return False
    try:
        from langsmith.utils import tracing_is_enabled

        return bool(tracing_is_enabled())
    except Exception:  # noqa: BLE001
        return False


def annotate_current_run(metadata: dict | None = None, tags: list[str] | None = None) -> None:
    """Attach metadata/tags to whichever traced span we're currently inside.
    A silent no-op when tracing is off or we're not inside a traced call."""
    if not LANGSMITH_AVAILABLE:
        return
    try:
        from langsmith.run_helpers import get_current_run_tree

        run = get_current_run_tree()
        if run is None:
            return
        if metadata:
            run.add_metadata(metadata)
        if tags:
            run.add_tags(tags)
    except Exception as exc:  # noqa: BLE001 - tracing must never break the app
        logger.debug("Could not annotate current run: %s", exc)


def flush_traces() -> None:
    """Traces are sent from a background thread. Short-lived scripts should
    call this before exiting or the last few traces can be lost."""
    if not tracing_enabled():
        return
    try:
        from langsmith.run_trees import get_cached_client

        get_cached_client().flush()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not flush LangSmith traces: %s", exc)


# --- helpers for @traceable(process_inputs=..., process_outputs=...) ---

def strip_self(inputs: dict) -> dict:
    return {k: v for k, v in inputs.items() if k != "self"}


def retrieved_to_documents(retrieved: list) -> dict:
    """Format retrieved chunks the way LangSmith's retriever view expects:
    a list of documents with page_content + metadata."""
    if not retrieved:  # None when the traced call raised; [] when nothing matched
        return {"documents": []}
    return {
        "documents": [
            {
                "page_content": item.chunk.text,
                "type": "Document",
                "metadata": {
                    "chunk_id": item.chunk.chunk_id,
                    "document_id": item.chunk.document_id,
                    "document_name": item.chunk.document_name,
                    "department": item.chunk.department,
                    "page": item.chunk.page,
                    "score": item.score,
                },
            }
            for item in retrieved
        ]
    }


def trace_retriever(name: str) -> Callable:
    """Decorator for a BaseRetriever.retrieve(self, query, top_k) method."""
    return traceable(
        name=name,
        run_type="retriever",
        process_inputs=strip_self,
        process_outputs=retrieved_to_documents,
    )


def summarize_query_result(output: Any) -> dict:
    """Compact view of a QueryResult for the root/generation spans. The full
    retrieved chunk text already appears on the retriever span, so repeating
    it here would just bloat every trace."""
    if output is None:  # LangSmith passes None when the traced call raised
        return {}
    data = output.model_dump() if hasattr(output, "model_dump") else dict(output)
    return {
        "answer": data.get("answer"),
        "citations": data.get("citations"),
        "num_retrieved": len(data.get("retrieved_chunks", [])),
        "strategy": data.get("strategy"),
        "latency_ms": data.get("latency_ms"),
    }


def summarize_generate_inputs(inputs: dict) -> dict:
    retrieved = inputs.get("retrieved") or []
    return {
        "question": inputs.get("question"),
        "num_retrieved": len(retrieved),
        "strategy": inputs.get("strategy"),
    }