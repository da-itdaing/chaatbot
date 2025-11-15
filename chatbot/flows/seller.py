"""Seller guidance flow."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..dataset.loader import load_seed_dataset
from ..retrieval import vector_store
from ..retrieval.query_parser import find_matches

LOGGER = logging.getLogger(__name__)
SEED_SOURCE = "seed_dataset"


def guide(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    vector_results = _vector_guide(query, limit)
    if vector_results:
        return vector_results
    return _seed_guide(query, limit)


def _vector_guide(query: str, limit: int) -> List[Dict[str, Any]]:
    if not vector_store.vector_support_enabled():
        return []
    try:
        return vector_store.search_seller_items(query, limit)
    except Exception as exc:  # pragma: no cover - 로그 용도
        LOGGER.warning("PGVector 셀러 검색 실패: %s", exc, exc_info=True)
        return []


def _seed_guide(query: str, limit: int) -> List[Dict[str, Any]]:
    data = load_seed_dataset()
    regions = find_matches(query, data["regions"], "region_id", "name")

    matching_zones = [zone for zone in data["zones"] if not regions or zone["region_id"] in regions]
    if not matching_zones:
        matching_zones = data["zones"][:limit]

    results: List[Dict[str, Any]] = []
    for zone in matching_zones[:limit]:
        approved_cells = [cell for cell in zone["cells"] if cell["status"] == "APPROVED"]
        cells = approved_cells if approved_cells else zone["cells"]
        if not cells:
            continue
        results.append(_format_seed_zone(zone, cells[0]))
    return results


def _format_seed_zone(zone: Dict[str, Any], cell: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "zone": zone["name"],
        "theme": zone.get("theme", "일반"),
        "features": zone.get("features", []),
        "suggested_cell": cell.get("label", "미정"),
        "cell_notice": cell.get("notice", "추가 안내 없음"),
        "next_step": "온라인 신청서 작성 후 서류 업로드",
        "source": SEED_SOURCE,
    }
