"""High-level entrypoints for the chatbot."""
from __future__ import annotations

from functools import lru_cache

from .graph.builder import build_app
from .graph.state import Role


@lru_cache(maxsize=1)
def get_app():
    return build_app()


def run_chatbot(role: Role, query: str) -> str:
    app = get_app()
    result = app.invoke({"role": role, "query": query})
    return result.get("response", "")
