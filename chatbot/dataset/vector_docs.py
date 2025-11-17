"""Utilities for transforming markets data into vector documents."""
from __future__ import annotations

from typing import Any, Dict, List

from langchain_core.documents import Document

from .loader import load_markets_dataset
from .market_utils import market_to_item


def _build_page_content(market: Dict[str, Any], item: Dict[str, Any]) -> str:
    attributes = ", ".join(item.get("attributes", []))
    amenities = ", ".join(item.get("amenities", []))
    location = item.get("location", "광주 전역")
    description = str(market.get("market_description") or item.get("description") or "").strip()
    rating = item.get("rating")
    rating_text = f"{rating:.1f}" if isinstance(rating, (int, float)) else "N/A"
    return (
        f"{item.get('name')} ({item.get('category')})\n"
        f"설명: {description or '정보 없음'}\n"
        f"특징: {attributes or '정보 없음'}\n"
        f"편의시설: {amenities or '정보 없음'}\n"
        f"위치: {location}\n"
        f"평점: {rating_text}"
    )


def build_market_documents() -> List[Document]:
    documents: List[Document] = []
    for market in load_markets_dataset():
        item = market_to_item(market)
        metadata = {**item, "doc_id": market.get("market_id"), "raw_locations": item.get("raw_locations", [])}
        documents.append(Document(page_content=_build_page_content(market, item), metadata=metadata))
    return documents