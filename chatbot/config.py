"""Configuration helpers for the Itdaing chatbot."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
MARKETS_DATA_PATH = BASE_DIR / "data" / "markets_seed.json"
ENV_FILE_PATH = BASE_DIR / ".env"
APP_ENV_VALUE = os.environ.get("APP_ENV", "dev").lower()
USE_ENV_FILE = APP_ENV_VALUE != "prod" and ENV_FILE_PATH.exists()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH if USE_ENV_FILE else None,
        env_file_encoding="utf-8",
        extra="allow",
    )

    app_env: str = os.environ.get("APP_ENV", "dev")
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    tavily_api_key: Optional[str] = None
    markets_seed_path: Path = MARKETS_DATA_PATH
    max_results: int = 5
    pgvector_connection: Optional[str] = None
    vector_collection: Optional[str] = None
    vector_dim: int = 1536
    pgvector_connect_timeout: int = 10
    langsmith_api_key: Optional[str] = None
    langsmith_project: Optional[str] = None
    langsmith_tracing: bool = False
    langsmith_endpoint: str = "https://api.smith.langchain.com"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
