"""FastAPI application exposing the Itdaing chatbot as an internal service."""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from fastapi import FastAPI
from pydantic import BaseModel, Field

from chatbot.app import get_app
from chatbot.config import get_settings
from chatbot.flows.consumer import recommend as recommend_consumer
from chatbot.formatting.response_builder import format_consumer

LOGGER = logging.getLogger("chatbot.api")

app = FastAPI(title="Itdaing Chatbot API", version="1.0.0")


class ChatHistoryMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatMetadata(BaseModel):
    roles: Optional[List[str]] = None
    client: Optional[str] = None
    locale: Optional[str] = None
    ip: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    bot_type: Literal["CONSUMER", "SELLER"]
    user_id: str
    session_id: str
    message: str
    history: List[ChatHistoryMessage] = Field(default_factory=list)
    metadata: Optional[ChatMetadata] = None
    limit: Optional[int] = Field(default=None, ge=1, le=25)


class ChatItem(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    category: Optional[str] = None
    attributes: List[str] = Field(default_factory=list)
    amenities: List[str] = Field(default_factory=list)
    location: Optional[str] = None
    description: Optional[str] = None
    rating: Optional[float] = None
    image_url: Optional[str] = None


class ChatMeta(BaseModel):
    source: Literal["rag", "basic"]
    model: Optional[str] = None
    tokens_prompt: Optional[int] = None
    tokens_completion: Optional[int] = None
    latency_ms: Optional[int] = None
    trace_id: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    bot_type: str
    session_id: str
    answer: str
    items: List[ChatItem]
    meta: ChatMeta


@app.get("/health")
def health() -> Dict[str, str]:
    """Simple health-check endpoint for ALB/systemd probes."""
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(payload: ChatRequest) -> ChatResponse:
    settings = get_settings()
    limit = payload.limit or settings.max_results
    limit = max(1, min(limit, settings.max_results))

    tags = _build_tags(payload)
    metadata = _build_metadata(payload)
    request_token = str(uuid4())

    if payload.bot_type == "CONSUMER":
        consumer_items = _safe_recommend(payload.message, limit)
        mapped_items = [_map_consumer_item(item) for item in consumer_items]
        rag_source = "rag" if consumer_items else "basic"

        llm_answer, latency_ms, langgraph_error = _invoke_langgraph_answer(
            payload.message,
            metadata,
            tags,
        )
        answer_text = llm_answer or format_consumer(consumer_items)

        extra_payload = {
            "tags": tags,
            "metadata": metadata,
            "history_size": len(payload.history),
        }
        if langgraph_error:
            extra_payload["langgraph_error"] = langgraph_error

        return ChatResponse(
            bot_type=payload.bot_type,
            session_id=payload.session_id,
            answer=answer_text,
            items=mapped_items,
            meta=ChatMeta(
                source=rag_source,
                model=settings.openai_model,
                latency_ms=latency_ms,
                trace_id=f"{payload.session_id}:{request_token}",
                extra=extra_payload,
            ),
        )

    seller_answer, latency_ms, langgraph_error = _invoke_langgraph_answer(
        payload.message,
        metadata,
        tags,
    )
    seller_answer = seller_answer or (
        "판매자 전용 챗봇이 곧 준비됩니다. 필요한 정보를 남겨주시면 최대한 빠르게 도와드릴게요!"
    )

    seller_extra = {
        "tags": tags,
        "metadata": metadata,
        "history_size": len(payload.history),
    }
    if langgraph_error:
        seller_extra["langgraph_error"] = langgraph_error

    return ChatResponse(
        bot_type=payload.bot_type,
        session_id=payload.session_id,
        answer=seller_answer,
        items=[],
        meta=ChatMeta(
            source="basic",
            model=settings.openai_model,
            latency_ms=latency_ms,
            trace_id=f"{payload.session_id}:{request_token}",
            extra=seller_extra,
        ),
    )


def _safe_recommend(query: str, limit: int) -> List[Dict[str, Any]]:
    try:
        return recommend_consumer(query, limit=limit)
    except Exception:  # pragma: no cover - safeguards external deps
        LOGGER.exception("consumer recommendation failed")
        return []


def _map_consumer_item(item: Dict[str, Any]) -> ChatItem:
    return ChatItem(
        id=item.get("source"),
        name=item.get("name"),
        category=item.get("category"),
        attributes=item.get("attributes", []) or [],
        amenities=item.get("amenities", []) or [],
        location=item.get("location"),
        description=item.get("description"),
        rating=item.get("rating"),
        image_url=item.get("image_url"),
    )


def _build_tags(payload: ChatRequest) -> List[str]:
    tags = ["itdaing-chatbot", payload.bot_type.lower()]
    if payload.metadata and payload.metadata.client:
        tags.append(f"client:{payload.metadata.client}")
    return tags


def _build_metadata(payload: ChatRequest) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "user_id": payload.user_id,
        "session_id": payload.session_id,
        "bot_type": payload.bot_type,
        "history": [msg.model_dump() for msg in payload.history],
    }
    if payload.metadata:
        data.update({
            "roles": payload.metadata.roles,
            "client": payload.metadata.client,
            "locale": payload.metadata.locale,
            "ip": payload.metadata.ip,
        })
        if payload.metadata.extra:
            data["extra"] = payload.metadata.extra
    return {key: value for key, value in data.items() if value not in (None, "", [])}


def _invoke_langgraph_answer(
    query: str, metadata: Dict[str, Any], tags: List[str]
) -> tuple[str, Optional[int], Optional[str]]:
    app_runner = get_app()
    config: Dict[str, Any] = {}
    if metadata:
        config["metadata"] = metadata
    if tags:
        config["tags"] = tags

    start = time.perf_counter()
    try:
        result = app_runner.invoke({"query": query}, config=config)
    except Exception as exc:  # pragma: no cover - depends on LangGraph runtime
        LOGGER.exception("LangGraph invocation failed")
        detail = getattr(exc, "detail", str(exc))
        return "", None, str(detail)
    latency_ms = int((time.perf_counter() - start) * 1000)
    return result.get("response", ""), latency_ms, None


__all__ = [
    "app",
]
