"""Utilities for transforming seed data into vector documents."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from langchain_core.documents import Document

from .loader import load_seed_dataset

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_PROMPT_JSON = ROOT_DIR / "data" / "test_prompts.json"


def _serialize(doc: Document) -> Dict[str, Any]:
    return {"page_content": doc.page_content, "metadata": doc.metadata}


def _build_consumer_documents(dataset: Dict[str, Any]) -> Tuple[List[Document], List[Dict[str, Any]]]:
    docs: List[Document] = []
    serialized: List[Dict[str, Any]] = []
    zones = {zone["zone_id"]: zone for zone in dataset.get("zones", [])}
    for popup in dataset.get("popups", []):
        zone = zones.get(popup.get("zone_id"))
        if not zone:
            continue
        region = zone.get("region_id", "unknown")
        features = ", ".join(zone.get("features", []))
        popup_features = ", ".join(popup.get("features", []))
        categories = ", ".join(popup.get("categories", []))
        styles = ", ".join(popup.get("styles", []))
        description = popup.get("description", "")
        page_content = (
            f"{popup.get('name')} | {zone.get('name')} ({region})\n"
            f"설명: {description}\n"
            f"카테고리: {categories}\n"
            f"스타일: {styles}\n"
            f"편의시설: {popup_features or features}\n"
            f"운영시간: {popup.get('operating_time', '상시')}"
        )
        metadata = {
            "doc_id": f"popup:{popup.get('popup_id')}",
            "type": "popup",
            "role": "consumer",
            "name": popup.get("name"),
            "zone": zone.get("name"),
            "region": region,
            "categories": popup.get("categories", []),
            "styles": popup.get("styles", []),
            "features": popup.get("features", zone.get("features", [])),
            "operating_time": popup.get("operating_time"),
            "status": popup.get("approval_status"),
            "cell_id": popup.get("cell_id"),
            "view_count": popup.get("view_count", 0),
        }
        doc = Document(page_content=page_content, metadata=metadata)
        docs.append(doc)
        serialized.append(_serialize(doc))
    return docs, serialized


def _build_seller_documents(dataset: Dict[str, Any]) -> Tuple[List[Document], List[Dict[str, Any]]]:
    docs: List[Document] = []
    serialized: List[Dict[str, Any]] = []
    for zone in dataset.get("zones", []):
        approved = [cell for cell in zone.get("cells", []) if cell.get("status") == "APPROVED"]
        pending = [cell for cell in zone.get("cells", []) if cell.get("status") == "PENDING"]
        first_cell = (approved or zone.get("cells", []))[:1]
        cell = first_cell[0] if first_cell else {}
        cell_label = cell.get("label", "미정")
        cell_notice = cell.get("notice", "추가 안내 없음")
        next_step = "온라인 신청서 작성 후 서류 업로드"
        page_content = (
            f"{zone.get('name')} ({zone.get('theme')})\n"
            f"지역: {zone.get('region_id')} | 수용 인원: {zone.get('max_capacity')}\n"
            f"승인 부스: {len(approved)} | 대기: {len(pending)}\n"
            f"주요 편의시설: {', '.join(zone.get('features', [])[:4])}\n"
            f"추천 부스: {cell_label} - {cell_notice}"
        )
        metadata = {
            "doc_id": f"zone:{zone.get('zone_id')}",
            "type": "zone",
            "role": "seller",
            "zone": zone.get("name"),
            "region": zone.get("region_id"),
            "theme": zone.get("theme"),
            "features": zone.get("features", []),
            "approved_cells": len(approved),
            "pending_cells": len(pending),
            "suggested_cell": cell_label,
            "cell_notice": cell_notice,
            "next_step": next_step,
        }
        doc = Document(page_content=page_content, metadata=metadata)
        docs.append(doc)
        serialized.append(_serialize(doc))
    return docs, serialized


def _load_prompt_records(path: Path) -> Sequence[Dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("prompts", [])


def _build_prompt_documents(prompts: Sequence[Dict[str, Any]]) -> Tuple[List[Document], List[Dict[str, Any]]]:
    docs: List[Document] = []
    serialized: List[Dict[str, Any]] = []
    for prompt in prompts:
        metadata = {
            "doc_id": f"prompt:{prompt.get('id')}",
            "type": "prompt",
            "role": prompt.get("role", "edge"),
            "section": prompt.get("section"),
        }
        doc = Document(page_content=prompt.get("text", ""), metadata=metadata)
        docs.append(doc)
        serialized.append(_serialize(doc))
    return docs, serialized


def build_vector_documents(include_prompts: bool = False, prompts_path: Path | None = None) -> Tuple[List[Document], List[Dict[str, Any]]]:
    dataset = load_seed_dataset()
    documents: List[Document] = []
    serialized: List[Dict[str, Any]] = []

    consumer_docs, consumer_serialized = _build_consumer_documents(dataset)
    documents.extend(consumer_docs)
    serialized.extend(consumer_serialized)

    seller_docs, seller_serialized = _build_seller_documents(dataset)
    documents.extend(seller_docs)
    serialized.extend(seller_serialized)

    if include_prompts:
        prompts = _load_prompt_records(prompts_path or DEFAULT_PROMPT_JSON)
        prompt_docs, prompt_serialized = _build_prompt_documents(prompts)
        documents.extend(prompt_docs)
        serialized.extend(prompt_serialized)

    return documents, serialized