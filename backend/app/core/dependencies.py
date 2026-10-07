import copy
import dataclasses
import threading
from collections import OrderedDict

from fastapi import Depends, HTTPException

from app.core.config import SAMPLE_WORKSPACE, Settings
from app.core.workspaces import workspace_settings
from app.pipelines.rag_pipeline import RAGPipeline
from app.pipelines.strategy import ChunkingStrategy, RetrievalStrategy, StrategyConfig

_pipelines: "OrderedDict[tuple[str, str, str], RAGPipeline]" = OrderedDict()
_lock = threading.Lock()


def _default_settings() -> Settings:
    from app.core.config import get_settings

    return get_settings()


def load_pipeline_for(
    chunking_strategy: ChunkingStrategy,
    retrieval_strategy: RetrievalStrategy,
    settings: Settings | None = None,
) -> RAGPipeline:
    """Raises FileNotFoundError if that combination's chunks/vector store
    haven't been built in this workspace. /query/compare catches this per strategy."""
    settings = settings or _default_settings()
    key = (settings.workspace_id, chunking_strategy, retrieval_strategy)
    with _lock:
        pipeline = _pipelines.get(key)
        if pipeline is not None:
            _pipelines.move_to_end(key)
            return pipeline
        pipeline = RAGPipeline(
            settings=settings.model_copy(update={"groq_api_key": "", "langchain_api_key": ""}),
            strategy=StrategyConfig(
                name=f"{chunking_strategy}_{retrieval_strategy}",
                chunking_strategy=chunking_strategy,
                retrieval_strategy=retrieval_strategy,
            ),
        )
        _pipelines[key] = pipeline
        while len(_pipelines) > max(1, settings.pipeline_cache_size):
            _pipelines.popitem(last=False)
        return pipeline


def bind_key(pipeline: RAGPipeline, settings: Settings) -> RAGPipeline:
    """A shallow copy of `pipeline` that generates answers with `settings.groq_api_key`.
    Raises GroqClientError if there is no key. The cached pipeline is untouched."""
    from app.generation.answer_generator import AnswerGenerator
    from app.generation.llm import GroqClient

    clone = copy.copy(pipeline)
    clone._answer_generator = AnswerGenerator(GroqClient(settings))
    return clone


def prepare_pipeline(pipeline: RAGPipeline, settings: Settings) -> RAGPipeline:
    """The pipeline to actually answer with for this caller.

    A visitor's own key, a non-default model, or a deployment that forbids the server key, gets a
    key-bound copy (`bind_key`). Otherwise the cached pipeline is used as is: its
    default generator already uses the server's own key (exactly the old
    single-user behaviour)."""
    if settings.user_supplied_key or settings.model_overridden or not settings.server_key_allowed:
        return bind_key(pipeline, settings)
    return pipeline


def loaded_pipelines(workspace_id: str | None = None) -> list[tuple[tuple[str, str], RAGPipeline]]:
    """[((chunking, retrieval), pipeline), ...]. With a workspace id, only that workspace's."""
    with _lock:
        return [
            ((c, r), p) for (w, c, r), p in _pipelines.items() if workspace_id is None or w == workspace_id
        ]


def clear_pipeline_cache(workspace_id: str | None = None) -> None:
    """Drop one workspace's cached pipelines (or all of them with no argument)."""
    with _lock:
        if workspace_id is None:
            _pipelines.clear()
            return
        for key in [k for k in _pipelines if k[0] == workspace_id]:
            del _pipelines[key]


def get_rag_pipeline(settings: Settings = Depends(workspace_settings)) -> RAGPipeline:
    """Default pipeline: fixed chunking + vector search."""
    try:
        return load_pipeline_for("fixed", "vector", settings)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def get_pipeline_for_strategy(
    retrieval_strategy: RetrievalStrategy,
    chunking_strategy: ChunkingStrategy = "fixed",
    settings: Settings | None = None,
) -> RAGPipeline:
    """HTTP-facing variant: turns a missing index into a 503."""
    try:
        return load_pipeline_for(chunking_strategy, retrieval_strategy, settings)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def with_top_k(pipeline: RAGPipeline, top_k: int | None) -> RAGPipeline:
    """Per-request top_k WITHOUT mutating the cached, shared pipeline.

    A shallow copy shares the heavy parts (embedder, vector store, retriever)
    but gets its own StrategyConfig, so one caller's top_k can't leak into
    another's (or race with a concurrent one)."""
    if top_k is None or top_k == pipeline.strategy.top_k:
        return pipeline
    clone = copy.copy(pipeline)
    clone.strategy = dataclasses.replace(pipeline.strategy, top_k=top_k)
    return clone
