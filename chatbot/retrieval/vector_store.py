"""Helpers for accessing the PGVector store."""
from __future__ import annotations

import socket
from functools import lru_cache
from typing import Any, Dict, List, Sequence

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url

from ..config import get_settings


class VectorStoreUnavailable(RuntimeError):
    """Raised when PGVector usage is requested but configuration is unavailable."""


def _require_settings() -> Any:
    settings = get_settings()
    if not (settings.pgvector_connection and settings.vector_collection and settings.openai_api_key):
        raise VectorStoreUnavailable("PGVector 설정이 완료되지 않았습니다.")
    return settings


_VECTOR_DISABLED = False
_VECTOR_PROBED = False


@lru_cache(maxsize=1)
def _get_embeddings() -> OpenAIEmbeddings:
    settings = _require_settings()
    return OpenAIEmbeddings(model=settings.openai_embedding_model, api_key=SecretStr(settings.openai_api_key))


@lru_cache(maxsize=1)
def get_vector_store() -> PGVector:
    settings = _require_settings()
    engine = create_engine(
        settings.pgvector_connection,
        connect_args={"connect_timeout": settings.pgvector_connect_timeout},
        pool_pre_ping=True,
    )
    return PGVector(
        connection=engine,
        collection_name=settings.vector_collection,
        embeddings=_get_embeddings(),
        use_jsonb=True,
    )


def _can_reach_pgvector(settings: Any) -> bool:
    try:
        url = make_url(settings.pgvector_connection)
    except Exception:
        return False
    host = url.host or "localhost"
    port = url.port or 5432
    try:
        with socket.create_connection((host, port), timeout=settings.pgvector_connect_timeout):
            return True
    except OSError:
        return False


def vector_support_enabled() -> bool:
    global _VECTOR_PROBED
    if _VECTOR_DISABLED:
        return False
    try:
        settings = _require_settings()
    except VectorStoreUnavailable:
        disable_vector_support()
        return False
    if not _VECTOR_PROBED:
        if not _can_reach_pgvector(settings):
            disable_vector_support()
            return False
        _VECTOR_PROBED = True
    return True


def disable_vector_support() -> None:
    global _VECTOR_DISABLED
    _VECTOR_DISABLED = True


def _normalize_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [value]
    return []


def _doc_to_consumer_item(doc: Document) -> Dict[str, Any]:
    meta = doc.metadata or {}
    location = meta.get("location")
    if not location:
        raw_locations = meta.get("raw_locations") or []
        if raw_locations:
            entry = raw_locations[0]
            city = entry.get("city") or ""
            district = entry.get("district") or ""
            location = " ".join(part for part in [city, district] if part).strip() or entry.get("address")
    description = meta.get("description")
    if not isinstance(description, str):
        lines = doc.page_content.splitlines()
        if len(lines) > 1:
            description = lines[1].split("설명:", 1)[-1].strip()
        else:
            description = ""
    rating = meta.get("rating")
    return {
        "name": meta.get("name") or doc.page_content.splitlines()[0].strip(),
        "category": meta.get("category", "플리마켓"),
        "attributes": _normalize_list(meta.get("attributes")),
        "amenities": _normalize_list(meta.get("amenities")),
        "location": location or "광주 전역",
        "description": description,
        "rating": rating,
        "source": meta.get("doc_id"),
    }


def _search(query: str, k: int) -> Sequence[Document]:
    store = get_vector_store()
    return store.similarity_search(query, k=k)


def search_consumer_items(query: str, limit: int) -> List[Dict[str, Any]]:
    docs = _search(query, limit)
    return [_doc_to_consumer_item(doc) for doc in docs]
