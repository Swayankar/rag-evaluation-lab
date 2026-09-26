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


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        extra="ignore"
    )

    # --- LLM (Groq) ---
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"
    groq_base_url: str = "https://api.groq.com/openai/v1"

    # --- LangSmith (wired up in a later phase) ---
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "rag-evaluation-lab"

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

    @property
    def raw_docs_path(self) -> Path:
        return Path(self.raw_docs_dir)

    @property
    def processed_chunks_path(self) -> Path:
        return Path(self.processed_chunks_dir)

    @property
    def vector_store_path(self) -> Path:
        return Path(self.vector_store_dir)

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


@lru_cache
def get_settings() -> Settings:
    return Settings()