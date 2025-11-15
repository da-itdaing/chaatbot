"""State definitions."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, TypedDict

from typing_extensions import Annotated


def merge_dicts(existing: Dict[str, Any] | None, update: Dict[str, Any] | None) -> Dict[str, Any]:
    merged: Dict[str, Any] = dict(existing or {})
    if update:
        merged.update(update)
    return merged


def extend_unique(existing: List[str] | None, update: List[str] | None) -> List[str]:
    base: List[str] = list(existing or [])
    seen = set(base)
    for item in update or []:
        if item not in seen:
            base.append(item)
            seen.add(item)
    return base

Role = Literal["consumer", "seller"]


class ChatbotState(TypedDict, total=False):
    role: Role
    query: str
    special_response: str
    bypass_retrieval: bool
    guardrail_triggered: bool
    guardrail_reason: str
    retrieval_tasks: List[str]
    completed_tasks: Annotated[List[str], extend_unique]
    evidence: Annotated[Dict[str, Any], merge_dicts]
    insights: Annotated[Dict[str, Any], merge_dicts]
    context_items: List[Dict[str, Any]]
    draft_response: str
    validation: Dict[str, Any]
    needs_correction: bool
    parallel_ready: bool
    response: str
