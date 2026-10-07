"""
Central application configuration.

Everything that will vary between environments (API keys, model names,
chunking defaults, paths) lives here so the rest of the codebase never
reads os.environ directly.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[3]

SAMPLE_WORKSPACE = "sample"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        extra="ignore"
    )

    # --- LLM (Groq) ---
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    # Models offered in the UI's dropdown (comma-separated). groq_model above is the default.
    groq_model_options: str = "openai/gpt-oss-20b, openai/gpt-oss-120b, qwen/qwen3.8-27b, llama-3.1-8b-instant, llama-3.3-70b-versatile"
    # May a visitor type any model name? In hosted mode this only applies to visitors using their OWN key
    # (so nobody can point your key at an expensive model).
    allow_custom_model: bool = True

    # --- LangSmith ---
    # Tracing is opt-in: it stays off unless LANGCHAIN_TRACING_V2=true AND a
    # key is set. Traces include prompts and retrieved document text, so
    # only turn it on if you're comfortable with that going to LangSmith.
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "rag-evaluation-lab"
    langsmith_endpoint: str = ""

    # --- Chunking defaults ---
    fixed_chunk_size: int = 500
    fixed_chunk_overlap: int = 50

    # Semantic chunking (Strategy B) tunables.
    semantic_breakpoint_percentile: float = 90.0
    semantic_min_chunk_tokens: int = 150
    semantic_max_chunk_tokens: int = 700

    # --- Embeddings ---
    # "sentence_transformers" for real semantic embeddings, or "hashing"
    # for the dependency-free fallback (also used automatically if
    # sentence-transformers isn't installed / its model can't download).
    embedding_backend: str = "sentence_transformers"
    embedding_model_name: str = "all-MiniLM-L6-v2"

    # --- Paths (relative to backend/) ---
    raw_docs_dir: str = "data/documents"
    processed_chunks_dir: str = "data/processed/chunks"
    vector_store_dir: str = "data/processed/vector_store"
    eval_dataset_dir: str = "data/evaluation"
    # Note: this one is NOT backend-relative like the others — it's the
    # project-root experiments/ folder from the architecture doc's layout,
    # a sibling of backend/, not a subdirectory of it.
    experiments_dir: str = "../experiments"

    # --- Hosting / workspaces ---
    app_mode: str = "local"
    workspaces_dir: str = "data/workspaces"
    cors_origins: str = "*"
    allow_server_key: bool | None = None

    workspace_ttl_days: int = 7  # private workspaces idle this long are deleted
    max_workspaces: int = 50  # total private workspaces that may exist at once
    max_workspaces_per_ip_per_hour: int = 5
    max_docs_per_workspace: int = 15
    max_workspace_mb: int = 60  # total PDF bytes per private workspace
    max_upload_mb: int = 25  # largest single PDF
    max_questions_per_workspace: int = 40
    max_concurrent_jobs: int = 2  # rebuilds / evaluations / experiments running at once, server-wide
    pipeline_cache_size: int = 16  # loaded (workspace, chunking, retrieval) pipelines kept in memory

    # --- Per-request fields (set by core/workspaces.py, never read from .env) ---
    workspace_id: str = SAMPLE_WORKSPACE
    workspace_read_only: bool = False
    default_groq_model: str = ""  # the server's default, kept when groq_model is replaced by the caller's choice
    model_overridden: bool = False  # True when the caller picked a model other than the default
    user_supplied_key: bool = False  # True when groq_api_key came from the visitor's X-Groq-Key header

    @property
    def model_choices(self) -> list[str]:
        """The default model first, then the configured options (no duplicates)."""
        extra = [m.strip() for m in self.groq_model_options.split(",") if m.strip()]
        return list(dict.fromkeys([self.default_groq_model or self.groq_model, *extra]))

    @property
    def is_hosted(self) -> bool:
        return self.app_mode == "hosted"

    @property
    def server_key_allowed(self) -> bool:
        if self.allow_server_key is None:
            return not self.is_hosted
        return self.allow_server_key

    @property
    def raw_docs_path(self) -> Path:
        return Path(self.raw_docs_dir)

    @property
    def processed_chunks_path(self) -> Path:
        return Path(self.processed_chunks_dir)

    @property
    def vector_store_path(self) -> Path:
        return Path(self.vector_store_dir)

    @property
    def eval_dataset_path(self) -> Path:
        return Path(self.eval_dataset_dir) / "questions.json"

    @property
    def eval_results_dir(self) -> Path:
        return Path(self.eval_dataset_dir) / "results"

    @property
    def experiments_results_dir(self) -> Path:
        return Path(self.experiments_dir) / "results"

    def chunks_path_for(self, chunking_strategy: str) -> Path:
        """Where a given chunking strategy's output lives. "fixed" keeps
        the original filename (fixed_chunks.json) for backward
        compatibility; other strategies (e.g. "semantic")
        get their own sibling file so both can exist side by side."""
        return self.processed_chunks_path / f"{chunking_strategy}_chunks.json"

    def vector_store_path_for(self, chunking_strategy: str) -> Path:
        """Where a given chunking strategy's vector store lives. "fixed"
        resolves to the exact same directory (no regression);
        other strategies get a sibling directory, e.g.
        data/processed/vector_store_semantic/."""
        if chunking_strategy == "fixed":
            return self.vector_store_path
        return self.vector_store_path.parent / f"{self.vector_store_path.name}_{chunking_strategy}"

    @property
    def is_sample(self) -> bool:
        return self.workspace_id == SAMPLE_WORKSPACE

    def paths_for_workspace(self, workspace_id: str) -> dict[str, str]:
        """Every data path of a private workspace, as Settings field values.
        Absolute, so they don't depend on the server's working directory."""
        root = (Path(self.workspaces_dir).resolve() / workspace_id)
        return {
            "raw_docs_dir": str(root / "documents"),
            "processed_chunks_dir": str(root / "processed" / "chunks"),
            "vector_store_dir": str(root / "processed" / "vector_store"),
            "eval_dataset_dir": str(root / "evaluation"),
            "experiments_dir": str(root / "experiments"),
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
