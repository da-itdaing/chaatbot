"""Helpers for accessing the PGVector store."""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, List, Sequence

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector
from pydantic import SecretStr
from sqlalchemy import create_engine

from ..config import get_settings


class VectorStoreUnavailable(RuntimeError):
    """Raised when PGVector usage is requested but configuration is missing."""


def _require_settings() -> Any:
    settings = get_settings()
    if not (settings.pgvector_connection and settings.vector_collection and settings.openai_api_key):
        raise VectorStoreUnavailable("PGVector 설정이 완료되지 않았습니다.")
    return settings


@lru_cache(maxsize=1)
def _get_embeddings() -> OpenAIEmbeddings:
    settings = _require_settings()
    return OpenAIEmbeddings(model=settings.openai_embedding_model, api_key=SecretStr(settings.openai_api_key))


@lru_cache(maxsize=1)
def get_vector_store() -> PGVector:
    settings = _require_settings()
    engine = create_engine(settings.pgvector_connection)
    return PGVector(
        connection=engine,
        collection_name=settings.vector_collection,
        embeddings=_get_embeddings(),
        use_jsonb=True,
    )


def vector_support_enabled() -> bool:
    try:
        _require_settings()
    except VectorStoreUnavailable:
        return False
    return True


def _normalize_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [value]
    return []


def _doc_to_consumer_item(doc: Document) -> Dict[str, Any]:
    meta = doc.metadata or {}
    return {
        "name": meta.get("name") or doc.page_content.split("|", 1)[0].strip(),
        "zone": meta.get("zone", "미정"),
        "cell": meta.get("cell_id", "-"),
        "categories": _normalize_list(meta.get("categories")),
        "styles": _normalize_list(meta.get("styles")),
        "features": _normalize_list(meta.get("features")),
        "operating_time": meta.get("operating_time", "상시"),
        "status": meta.get("status", "APPROVED"),
        "source": meta.get("doc_id"),
    }


def _doc_to_seller_item(doc: Document) -> Dict[str, Any]:
    meta = doc.metadata or {}
    return {
        "zone": meta.get("zone", "미정"),
        "theme": meta.get("theme", "일반"),
        "features": _normalize_list(meta.get("features")),
        "suggested_cell": meta.get("suggested_cell", "-"),
        "cell_notice": meta.get("cell_notice", "문의 바랍니다."),
        "next_step": meta.get("next_step", "온라인 신청서 작성 후 서류 업로드"),
        "source": meta.get("doc_id"),
    }


def _search(query: str, k: int, role: str) -> Sequence[Document]:
    store = get_vector_store()
    return store.similarity_search(query, k=k, filter={"role": role})


def search_consumer_items(query: str, limit: int) -> List[Dict[str, Any]]:
    docs = _search(query, limit, role="consumer")
    return [_doc_to_consumer_item(doc) for doc in docs]


def search_seller_items(query: str, limit: int) -> List[Dict[str, Any]]:
    docs = _search(query, limit, role="seller")
    return [_doc_to_seller_item(doc) for doc in docs]
