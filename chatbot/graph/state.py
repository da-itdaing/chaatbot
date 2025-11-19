"""Typed state container for the LangGraph chatbot flow."""
from __future__ import annotations

from typing import List, TypedDict

from langchain_core.documents import Document


class AgentState(TypedDict, total=False):
    """Runtime state shared across the graph."""

    query: str
    context: List["Document"]
    answer: str
    response: str
