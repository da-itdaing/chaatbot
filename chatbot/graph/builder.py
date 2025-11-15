"""LangGraph builder for the chatbot with parallel retrieval + Self-RAG."""
from __future__ import annotations

from typing import Any, Dict, List

from langgraph.graph import END, START, StateGraph

from ..config import get_settings
from ..dataset.loader import load_seed_dataset
from ..flows.consumer import recommend
from ..flows.seller import guide
from ..formatting.response_builder import format_consumer, format_seller
from ..guardrails import rules
from ..retrieval.query_parser import find_matches
from .state import ChatbotState, Role

SELLER_KEYWORDS = ["입점", "판매", "부스", "출점", "셀러", "신청"]
WEB_KEYWORDS = ["웹", "검색", "날씨", "트렌드", "리뷰", "후기"]
SMALLTALK_KEYWORDS = [
    "너",
    "소개",
    "사람",
    "ai",
    "에이아이",
    "모델",
    "매뉴얼",
    "정체",
    "스스로",
    "생각",
]


def _detect_role(query: str, fallback: Role) -> Role:
    lower_query = query.lower()
    for keyword in SELLER_KEYWORDS:
        if keyword in lower_query:
            return "seller"
    return fallback


def _mark_completed(existing: List[str] | None, task: str) -> List[str]:
    completed = list(existing or [])
    if task not in completed:
        completed.append(task)
    return completed


def _ensure_dict(mapping: Dict[str, Any] | None) -> Dict[str, Any]:
    return dict(mapping) if mapping else {}


def _maybe_build_smalltalk(query: str, role: Role) -> str | None:
    normalized = (query or "").strip()
    if not normalized:
        return None
    lower = normalized.lower()
    if not any(keyword in lower for keyword in SMALLTALK_KEYWORDS):
        return None
    role_hint = "판매자 분" if role == "seller" else "방문객 분"
    return (
        f"저는 광주 지역 팝업·플리마켓 정보를 정리해 드리는 AI 코디네이터예요. "
        f"{role_hint}이 궁금해할 만한 존과 셀 상황을 LangGraph 워크플로에서 정리해서 전달하고 있어요. "
        "궁금한 행사나 원하는 분위기를 알려주시면 바로 추천을 이어갈게요!"
    )


def ingest_node(state: ChatbotState) -> ChatbotState:
    query = (state.get("query") or "").strip()
    role = state.get("role") or _detect_role(query, "consumer")
    return {"query": query, "role": role}


def guardrail_node(state: ChatbotState) -> ChatbotState:
    result = rules.evaluate(state.get("query", ""))
    if result.triggered:
        return {
            "guardrail_triggered": True,
            "guardrail_reason": result.reason or "",
            "response": result.response or "요청을 처리할 수 없습니다.",
        }
    return {"guardrail_triggered": False, "guardrail_reason": ""}


def intent_router_node(state: ChatbotState) -> ChatbotState:
    query = state.get("query", "")
    role = _detect_role(query, state.get("role", "consumer"))
    insights = _ensure_dict(state.get("insights"))
    smalltalk = _maybe_build_smalltalk(query, role)
    insights["intent"] = {
        "role": role,
        "confidence": 0.8 if role == state.get("role") else 0.6,
        "type": "smalltalk" if smalltalk else "domain",
    }
    payload: Dict[str, Any] = {"role": role, "insights": insights}
    if smalltalk:
        payload.update({"special_response": smalltalk, "bypass_retrieval": True})
    return payload


def retrieval_planner_node(state: ChatbotState) -> ChatbotState:
    if state.get("bypass_retrieval"):
        insights = _ensure_dict(state.get("insights"))
        insights["retrieval_plan"] = []
        return {
            "retrieval_tasks": [],
            "completed_tasks": [],
            "insights": insights,
        }
    query = state.get("query", "").lower()
    tasks: List[str] = ["vector", "metadata"]
    if any(keyword in query for keyword in WEB_KEYWORDS):
        tasks.append("web")
    insights = _ensure_dict(state.get("insights"))
    insights["retrieval_plan"] = tasks
    return {
        "retrieval_tasks": tasks,
        "completed_tasks": [],
        "insights": insights,
        "evidence": _ensure_dict(state.get("evidence")),
    }


def vector_retrieval_node(state: ChatbotState) -> ChatbotState:
    if "vector" not in state.get("retrieval_tasks", []):
        return {}
    settings = get_settings()
    query = state.get("query", "")
    role = state.get("role", "consumer")
    if role == "seller":
        items = guide(query, limit=settings.max_results)
    else:
        items = recommend(query, limit=settings.max_results)
    evidence = _ensure_dict(state.get("evidence"))
    evidence["vector"] = items
    return {
        "context_items": items,
        "completed_tasks": _mark_completed(state.get("completed_tasks"), "vector"),
        "evidence": evidence,
    }


def _summarize_zone_metadata(query: str, limit: int = 3) -> List[Dict[str, Any]]:
    data = load_seed_dataset()
    region_ids = find_matches(query, data["regions"], "region_id", "name")
    summaries: List[Dict[str, Any]] = []
    for zone in data["zones"]:
        if region_ids and zone["region_id"] not in region_ids:
            continue
        approved = sum(1 for cell in zone["cells"] if cell["status"] == "APPROVED")
        pending = sum(1 for cell in zone["cells"] if cell["status"] == "PENDING")
        summaries.append(
            {
                "zone": zone["name"],
                "region_id": zone["region_id"],
                "approved_cells": approved,
                "waitlist": pending,
                "amenities": zone["features"][:3],
            }
        )
    if not summaries:
        summaries = [
            {
                "zone": zone["name"],
                "region_id": zone["region_id"],
                "approved_cells": sum(1 for cell in zone["cells"] if cell["status"] == "APPROVED"),
                "waitlist": sum(1 for cell in zone["cells"] if cell["status"] == "PENDING"),
                "amenities": zone["features"][:3],
            }
            for zone in data["zones"][:limit]
        ]
    return summaries[:limit]


def metadata_scan_node(state: ChatbotState) -> ChatbotState:
    if "metadata" not in state.get("retrieval_tasks", []):
        return {}
    summaries = _summarize_zone_metadata(state.get("query", ""))
    evidence = _ensure_dict(state.get("evidence"))
    evidence["metadata"] = summaries
    insights = _ensure_dict(state.get("insights"))
    insights["metadata_sample"] = summaries
    return {
        "completed_tasks": _mark_completed(state.get("completed_tasks"), "metadata"),
        "evidence": evidence,
        "insights": insights,
    }


def _synthesize_web_updates(query: str, missing_facets: List[str]) -> List[Dict[str, str]]:
    facets = missing_facets or ["행사 일정", "셀러 후기", "교통 접근"]
    return [
        {
            "source": "search",
            "title": f"{facet} 참고",
            "snippet": f"{query[:30]}... 관련 {facet} 최신 리포트를 확인했습니다.",
        }
        for facet in facets[:3]
    ]


def web_search_node(state: ChatbotState) -> ChatbotState:
    if "web" not in state.get("retrieval_tasks", []):
        return {}
    missing = state.get("validation", {}).get("missing_facets", [])
    results = _synthesize_web_updates(state.get("query", ""), missing)
    evidence = _ensure_dict(state.get("evidence"))
    evidence["web"] = results
    return {
        "completed_tasks": _mark_completed(state.get("completed_tasks"), "web"),
        "evidence": evidence,
    }


def parallel_sync_node(state: ChatbotState) -> ChatbotState:
    tasks = state.get("retrieval_tasks", [])
    completed = state.get("completed_tasks", [])
    ready = not tasks or set(completed) >= set(tasks)
    return {"parallel_ready": ready}


def route_after_parallel(state: ChatbotState) -> str:
    return "ready" if state.get("parallel_ready") else "pending"


def await_parallel_node(state: ChatbotState) -> ChatbotState:
    # 단순히 상태를 유지하며 다른 분기가 끝나기를 기다린다.
    return {}


def draft_response_node(state: ChatbotState) -> ChatbotState:
    if state.get("special_response"):
        return {"draft_response": state["special_response"]}
    items = state.get("context_items") or state.get("evidence", {}).get("vector") or []
    if not items:
        return {
            "draft_response": "조건에 맞는 장소를 아직 찾지 못했어요. 다른 분위기나 지역을 알려주시면 다시 찾아볼게요.",
        }
    if state.get("role") == "seller":
        draft = format_seller(items)
    else:
        draft = format_consumer(items)
    return {"draft_response": draft}


def self_rag_validation_node(state: ChatbotState) -> ChatbotState:
    if state.get("bypass_retrieval") or state.get("special_response"):
        return {"validation": None, "needs_correction": False}
    draft = state.get("draft_response", "")
    context = state.get("context_items", [])
    query = state.get("query", "").lower()
    required_terms = []
    if any(keyword in query for keyword in ["야간", "밤", "night"]):
        required_terms.append("야간")
    if "프리미엄" in query:
        required_terms.append("프리미엄")
    if "셀러" in query or state.get("role") == "seller":
        required_terms.append("셀")
    missing = [term for term in required_terms if term not in draft]
    coverage = round(min(1.0, len(context) / max(1, get_settings().max_results)), 2)
    status = "fail" if missing or coverage < 0.4 else "pass"
    validation = {
        "status": status,
        "coverage": coverage,
        "missing_facets": missing,
    }
    return {"validation": validation, "needs_correction": status == "fail"}


def route_after_validation(state: ChatbotState) -> str:
    return "correction" if state.get("needs_correction") else "format"


def corrective_rag_node(state: ChatbotState) -> ChatbotState:
    missing = state.get("validation", {}).get("missing_facets", [])
    augmented_query = f"{state.get('query', '')} {' '.join(missing)}".strip()
    settings = get_settings()
    role = state.get("role", "consumer")
    if role == "seller":
        items = guide(augmented_query or state.get("query", ""), limit=settings.max_results)
    else:
        items = recommend(augmented_query or state.get("query", ""), limit=settings.max_results)
    insights = _ensure_dict(state.get("insights"))
    insights["corrections"] = {"missing": missing, "applied": len(missing) > 0}
    validation = _ensure_dict(state.get("validation"))
    validation["status"] = "corrected"
    return {
        "context_items": items,
        "needs_correction": False,
        "insights": insights,
        "validation": validation,
    }


def formatter_node(state: ChatbotState) -> ChatbotState:
    if state.get("guardrail_triggered"):
        return {}
    if state.get("special_response"):
        return {"response": state["special_response"]}
    items = state.get("context_items", [])
    if not items:
        return {"response": "요청 조건에 맞는 정보를 찾지 못했습니다. 다른 조건으로 다시 문의해 주세요."}
    if state.get("role") == "seller":
        body = format_seller(items)
    else:
        body = format_consumer(items)
    validation = state.get("validation") or {}
    insights = state.get("insights", {})
    corrections = insights.get("corrections") or {}
    note: str | None = None
    if validation.get("status") == "fail":
        note = "요청한 조건을 더 강조하려면 구체적인 키워드를 알려주세요. 부족한 부분을 바로 찾아볼게요."
    elif corrections.get("applied"):
        note = "추가로 강조된 조건을 반영해 다시 정리했습니다."
    response = body if not note else f"{body}\n\n{note}"
    return {"response": response}


def build_app():
    graph = StateGraph(ChatbotState)
    graph.add_node("ingest", ingest_node)
    graph.add_node("guardrail", guardrail_node)
    graph.add_node("intent_router", intent_router_node)
    graph.add_node("retrieval_planner", retrieval_planner_node)
    graph.add_node("vector_retrieval", vector_retrieval_node)
    graph.add_node("metadata_scan", metadata_scan_node)
    graph.add_node("web_search", web_search_node)
    graph.add_node("parallel_sync", parallel_sync_node)
    graph.add_node("await_parallel", await_parallel_node)
    graph.add_node("draft_response", draft_response_node)
    graph.add_node("self_rag_validation", self_rag_validation_node)
    graph.add_node("corrective_rag", corrective_rag_node)
    graph.add_node("format_response", formatter_node)

    graph.add_edge(START, "ingest")
    graph.add_edge("ingest", "guardrail")
    graph.add_conditional_edges(
        "guardrail",
        lambda state: "blocked" if state.get("guardrail_triggered") else "pass",
        {"blocked": "format_response", "pass": "intent_router"},
    )
    graph.add_edge("intent_router", "retrieval_planner")
    graph.add_edge("retrieval_planner", "vector_retrieval")
    graph.add_edge("retrieval_planner", "metadata_scan")
    graph.add_edge("retrieval_planner", "web_search")
    graph.add_edge("vector_retrieval", "parallel_sync")
    graph.add_edge("metadata_scan", "parallel_sync")
    graph.add_edge("web_search", "parallel_sync")
    graph.add_conditional_edges(
        "parallel_sync",
        route_after_parallel,
        {"ready": "draft_response", "pending": "await_parallel"},
    )
    graph.add_edge("draft_response", "self_rag_validation")
    graph.add_conditional_edges(
        "self_rag_validation",
        route_after_validation,
        {"correction": "corrective_rag", "format": "format_response"},
    )
    graph.add_edge("corrective_rag", "format_response")
    graph.add_edge("format_response", END)
    return graph.compile()
