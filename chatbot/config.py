"""Configuration helpers for the Itdaing chatbot."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "itdaing_seed.json"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="allow")

    app_env: str = "dev"
    openai_api_key: Optional[str] = None
    pgvector_connection: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    vector_collection: Optional[str] = None
    seed_path: Path = DATA_PATH
    max_results: int = 5


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
