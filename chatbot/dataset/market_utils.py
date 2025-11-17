"""Helper routines for shaping markets dataset records."""
from __future__ import annotations

from typing import Any, Dict, List


def normalize_str_list(value: object) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if isinstance(item, (str, int, float)) and str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def normalize_location_list(value: object) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    cleaned: List[Dict[str, Any]] = []
    for entry in value:
        if isinstance(entry, dict):
            cleaned.append(entry)
    return cleaned


def format_location_label(locations: List[Dict[str, Any]]) -> str:
    labels: List[str] = []
    for loc in locations:
        city = str(loc.get("city", "")).strip()
        district = str(loc.get("district", "")).strip()
        address = str(loc.get("address", "")).strip()
        zone = str(loc.get("zone_id", "")).strip()
        if city or district:
            labels.append(" ".join(part for part in [city, district] if part))
        elif address:
            labels.append(address)
        elif zone:
            labels.append(zone)
    return ", ".join(label for label in labels if label)


def short_description(value: object, limit: int = 140) -> str:
    if not isinstance(value, str):
        return ""
    squashed = " ".join(value.split())
    if len(squashed) <= limit:
        return squashed
    trimmed = squashed[: limit - 1].rstrip()
    return f"{trimmed}..."


def market_to_item(market: Dict[str, Any]) -> Dict[str, Any]:
    locations = normalize_location_list(market.get("market_location"))
    return {
        "name": str(market.get("market_name") or "이름 미정"),
        "category": str(market.get("market_category") or "플리마켓"),
        "attributes": normalize_str_list(market.get("market_attribute")),
        "amenities": normalize_str_list(market.get("market_ameni")),
        "location": format_location_label(locations) or "광주 전역",
        "rating": market.get("market_rating"),
        "description": short_description(market.get("market_description")),
        "source": market.get("market_id"),
        "raw_locations": locations,
    }


def score_market(query: str, market: Dict[str, Any]) -> float:
    lowered = (query or "").lower()
    if not lowered:
        return 0.0
    score = 0.0
    category = str(market.get("market_category") or "").lower()
    if category and category in lowered:
        score += 3.0
    for attribute in normalize_str_list(market.get("market_attribute")):
        if attribute.lower() in lowered:
            score += 1.0
    for amenity in normalize_str_list(market.get("market_ameni")):
        if amenity.lower() in lowered:
            score += 0.5
    for location in normalize_location_list(market.get("market_location")):
        city = str(location.get("city", "")).lower()
        district = str(location.get("district", "")).lower()
        address = str(location.get("address", "")).lower()
        for token in filter(None, [city, district, address]):
            if token and token in lowered:
                score += 1.5
                break
    description = str(market.get("market_description") or "").lower()
    if description and lowered in description:
        score += 0.5
    rating = market.get("market_rating")
    if isinstance(rating, (int, float)):
        score += min(1.0, rating / 5.0)
    return score


__all__ = [
    "market_to_item",
    "normalize_location_list",
    "normalize_str_list",
    "score_market",
]
