"""State definitions."""
from __future__ import annotations

from typing import Any, Dict, List, TypedDict

from typing_extensions import Annotated


def merge_dicts(existing: Dict[str, Any] | None, update: Dict[str, Any] | None) -> Dict[str, Any]:
    merged: Dict[str, Any] = dict(existing or {})
    if update:
        merged.update(update)
    return merged
class ChatbotState(TypedDict, total=False):
    query: str
    special_response: str
    bypass_retrieval: bool
    analysis: Annotated[Dict[str, Any], merge_dicts]
    evidence: Annotated[Dict[str, Any], merge_dicts]
    insights: Annotated[Dict[str, Any], merge_dicts]
    context_items: List[Dict[str, Any]]
    draft_response: str
    validation: Dict[str, Any]
    needs_correction: bool
    grade: Annotated[Dict[str, Any], merge_dicts]
    response: str
