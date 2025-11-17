"""Configuration helpers for the Itdaing chatbot."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
MARKETS_DATA_PATH = BASE_DIR / "data" / "markets_seed.json"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="allow")

    app_env: str = "dev"
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    markets_seed_path: Path = MARKETS_DATA_PATH
    max_results: int = 5
    pgvector_connection: Optional[str] = None
    vector_collection: Optional[str] = None
    pgvector_connect_timeout: int = 10
    langsmith_api_key: Optional[str] = None
    langsmith_project: Optional[str] = None
    langsmith_tracing: bool = False
    langsmith_endpoint: str = "https://api.smith.langchain.com"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
