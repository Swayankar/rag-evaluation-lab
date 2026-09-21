"""
Central application configuration.

Everything that will vary between environments (API keys, model names,
chunking defaults, paths) lives here so the rest of the codebase never
reads os.environ directly.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- LLM (Grok / xAI) ---
    grok_api_key: str = ""
    grok_model: str = "grok-2-latest"
    grok_base_url: str = "https://api.x.ai/v1"

    # --- LangSmith (wired up in a later phase) ---
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "rag-evaluation-lab"

    # --- Chunking defaults ---
    fixed_chunk_size: int = 500
    fixed_chunk_overlap: int = 50

    # --- Paths (relative to backend/) ---
    raw_docs_dir: str = "data/documents"
    processed_chunks_dir: str = "data/processed/chunks"

    @property
    def raw_docs_path(self) -> Path:
        return Path(self.raw_docs_dir)

    @property
    def processed_chunks_path(self) -> Path:
        return Path(self.processed_chunks_dir)


@lru_cache
def get_settings() -> Settings:
    return Settings()
