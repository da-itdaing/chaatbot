"""Consumer recommendation flow."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..dataset.loader import load_seed_dataset
from ..retrieval import vector_store
from ..retrieval.query_parser import find_matches

LOGGER = logging.getLogger(__name__)
SEED_SOURCE = "seed_dataset"


def recommend(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    vector_results = _vector_recommend(query, limit)
    if vector_results:
        return vector_results
    return _seed_recommend(query, limit)


def _vector_recommend(query: str, limit: int) -> List[Dict[str, Any]]:
    if not vector_store.vector_support_enabled():
        return []
    try:
        return vector_store.search_consumer_items(query, limit)
    except Exception as exc:  # pragma: no cover - 로그 용도
        LOGGER.warning("PGVector 추천 검색 실패: %s", exc, exc_info=True)
        return []


def _seed_recommend(query: str, limit: int) -> List[Dict[str, Any]]:
    data = load_seed_dataset()
    regions = find_matches(query, data["regions"], "region_id", "name")
    categories = find_matches(query, data["categories"], "category_id", "name")
    styles = find_matches(query, data["styles"], "style_id", "name")
    feature_matches = find_matches(query, data["features"], "feature_id", "name")

    results: List[Dict[str, Any]] = []
    for popup in data["popups"]:
        zone = next((z for z in data["zones"] if z["zone_id"] == popup["zone_id"]), None)
        if not zone:
            continue
        if regions and zone["region_id"] not in regions:
            continue
        if categories and not any(cat in popup["categories"] for cat in categories):
            continue
        if styles and not any(style in popup["styles"] for style in styles):
            continue
        if feature_matches and not any(feat in popup["features"] for feat in feature_matches):
            continue
        results.append(_format_seed_popup(popup, zone))
        if len(results) >= limit:
            break

    if not results:
        sorted_popups = sorted(
            (_format_seed_popup(popup, _find_zone(data, popup)) for popup in data["popups"]),
            key=lambda item: item["name"],
        )
        results = sorted_popups[:limit]
    return results


def _find_zone(data: Dict[str, Any], popup: Dict[str, Any]) -> Dict[str, Any]:
    return next((z for z in data["zones"] if z["zone_id"] == popup["zone_id"]), {"name": "알 수 없음"})


def _format_seed_popup(popup: Dict[str, Any], zone: Dict[str, Any] | None) -> Dict[str, Any]:
    zone_name = zone["name"] if zone and "name" in zone else "알 수 없음"
    return {
        "name": popup["name"],
        "zone": zone_name,
        "cell": popup.get("cell_id", "-"),
        "categories": popup.get("categories", []),
        "styles": popup.get("styles", []),
        "features": popup.get("features", []),
        "status": popup.get("approval_status"),
        "operating_time": popup.get("operating_time"),
        "source": SEED_SOURCE,
    }
