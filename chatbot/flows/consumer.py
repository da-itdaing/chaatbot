"""Consumer recommendation flow powered purely by semantic search."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..retrieval import vector_store

LOGGER = logging.getLogger(__name__)


def recommend(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    if not vector_store.vector_support_enabled():
        return []
    try:
        items = vector_store.search_consumer_items(query, limit)
    except Exception as exc:  # pragma: no cover - 로그 용도
        LOGGER.warning("PGVector 추천 검색 실패: %s", exc, exc_info=True)
        items = []
    return items

