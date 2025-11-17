"""High-level entrypoints for the chatbot."""
from __future__ import annotations

import os
from functools import lru_cache

from .config import get_settings
from .graph.builder import build_app


def _configure_tracing() -> None:
    settings = get_settings()
    if not settings.langsmith_api_key:
        return
    env_defaults = {
        "LANGCHAIN_API_KEY": settings.langsmith_api_key,
        "LANGCHAIN_ENDPOINT": settings.langsmith_endpoint,
        "LANGCHAIN_TRACING_V2": "true" if settings.langsmith_tracing else None,
    }
    if settings.langsmith_project:
        env_defaults["LANGCHAIN_PROJECT"] = settings.langsmith_project
    for key, value in env_defaults.items():
        if value and not os.environ.get(key):
            os.environ[key] = value


@lru_cache(maxsize=1)
def get_app():
    _configure_tracing()
    return build_app()


def run_chatbot(query: str) -> str:
    app = get_app()
    result = app.invoke({"query": query})
    return result.get("response", "")
