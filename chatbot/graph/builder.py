"""LangGraph builder for the chatbot with semantic query analysis + Self-RAG."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Sequence

from langgraph.graph import END, START, StateGraph

from ..config import get_settings
from ..flows.consumer import recommend
from ..formatting.response_builder import format_consumer
from .state import ChatbotState
CONSUMER_KEYWORDS = [
    "플리마켓",
    "마켓",
    "셀러",
    "부스",
    "행사",
    "팝업",
    "공연",
    "체험",
    "추천",
    "광주",
    "남구",
    "북구",
    "페스티벌",
    "벼룩시장",
]
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
    "시간",
    "날씨",
]
OFF_DOMAIN_KEYWORDS = ["날씨", "검색", "뉴스", "정치", "주식", "코인"]
def _ensure_dict(mapping: Dict[str, Any] | None) -> Dict[str, Any]:
    return dict(mapping) if mapping else {}


def _count_hits(text: str, keywords: Sequence[str]) -> int:
    lowered = text.lower()
    return sum(1 for keyword in keywords if keyword in lowered)


def _tokenize(text: str) -> set[str]:
    return {token for token in text.lower().replace("\n", " ").split() if token}


def _overlap_score(query_tokens: set[str], candidate: str) -> float:
    if not query_tokens:
        return 0.0
    candidate_tokens = _tokenize(candidate)
    if not candidate_tokens:
        return 0.0
    overlap = len(query_tokens & candidate_tokens)
    return overlap / max(len(query_tokens), 1)


def ingest_node(state: ChatbotState) -> ChatbotState:
    query = (state.get("query") or "").strip()
    return {"query": query}


def _build_smalltalk_message(query: str) -> str:
    normalized = query.strip()
    if not normalized:
        return (
            "저는 광주 지역 플리마켓과 팝업 정보를 정리해 드리는 AI 코디네이터예요. "
            "원하시는 분위기나 시간대를 알려주시면 바로 살펴볼게요!"
        )
    return (
        "저는 광주 지역 플리마켓·팝업 정보를 추천해 드리는 AI예요. "
        f"'{normalized}'에 대해 이야기해 보고 싶다면 어떤 행사나 분위기를 찾는지도 함께 알려주세요."
    )


def query_analysis_node(state: ChatbotState) -> ChatbotState:
    query = state.get("query", "")
    normalized = query.lower()
    consumer_hits = _count_hits(normalized, CONSUMER_KEYWORDS)
    smalltalk_hits = _count_hits(normalized, SMALLTALK_KEYWORDS)
    off_domain_hits = _count_hits(normalized, OFF_DOMAIN_KEYWORDS)
    index_relevant = bool(query) and consumer_hits >= max(smalltalk_hits, off_domain_hits)
    confidence = min(1.0, 0.35 + 0.15 * consumer_hits)
    if not index_relevant and query:
        confidence = max(0.0, confidence - 0.2)
    analysis = {
        "normalized": normalized,
        "consumer_hits": consumer_hits,
        "smalltalk_hits": smalltalk_hits,
        "off_domain_hits": off_domain_hits,
        "index_relevant": index_relevant,
        "confidence": round(confidence, 2),
        "reason": "consumer_intent" if index_relevant else "off_domain_or_smalltalk",
    }
    insights = _ensure_dict(state.get("insights"))
    insights["analysis"] = analysis
    return {"analysis": analysis, "insights": insights}


def route_after_query_analysis(state: ChatbotState) -> str:
    analysis = state.get("analysis") or {}
    return "retrieval" if analysis.get("index_relevant") else "smalltalk"


def general_response_node(state: ChatbotState) -> ChatbotState:
    query = state.get("query", "")
    analysis = state.get("analysis") or {}
    grade = state.get("grade") or {}
    if not analysis.get("index_relevant"):
        message = _build_smalltalk_message(query)
    elif grade.get("status") == "retry":
        message = (
            "질문을 이해했지만 적절한 장소를 아직 찾지 못했어요. "
            "조금 더 구체적인 분위기나 지역을 알려주시면 다시 찾아볼게요."
        )
    else:
        message = (
            "간단한 안내만 필요한 것으로 분석되어 짧게 답변드렸어요. "
            "필요하시면 구체적인 조건을 알려주세요."
        )
    return {"special_response": message, "bypass_retrieval": True}


def vector_retrieval_node(state: ChatbotState) -> ChatbotState:
    settings = get_settings()
    query = state.get("query", "")
    items = recommend(query, limit=settings.max_results)
    evidence = _ensure_dict(state.get("evidence"))
    evidence["vector"] = items
    return {
        "context_items": items,
        "evidence": evidence,
    }


def doc_grader_node(state: ChatbotState) -> ChatbotState:
    query = state.get("query", "")
    items = state.get("context_items") or []
    query_tokens = _tokenize(query)
    if not items:
        grade = {"status": "retry", "score": 0.0, "reason": "no_items"}
    else:
        overlaps: List[float] = []
        for item in items:
            text = " ".join(
                str(part)
                for part in [item.get("name"), item.get("description"), " ".join(item.get("attributes", []))]
                if part
            )
            overlaps.append(_overlap_score(query_tokens, text))
        best_overlap = max(overlaps) if overlaps else 0.0
        threshold = 0.18 if len(query_tokens) > 3 else 0.12
        status = "pass" if best_overlap >= threshold else "retry"
        grade = {"status": status, "score": round(best_overlap, 2), "reason": "overlap"}
    insights = _ensure_dict(state.get("insights"))
    insights["grade"] = grade
    return {"grade": grade, "insights": insights}


def route_after_grade(state: ChatbotState) -> str:
    grade = state.get("grade") or {}
    return "answer" if grade.get("status") == "pass" else "fallback"


def draft_response_node(state: ChatbotState) -> ChatbotState:
    items = state.get("context_items") or state.get("evidence", {}).get("vector") or []
    if not items:
        return {
            "draft_response": "조건에 맞는 장소를 아직 찾지 못했어요. 다른 분위기나 지역을 알려주시면 다시 찾아볼게요.",
        }
    return {"draft_response": format_consumer(items)}


def self_rag_validation_node(state: ChatbotState) -> ChatbotState:
    if state.get("bypass_retrieval") or state.get("special_response"):
        return {"validation": {}, "needs_correction": False}
    draft = state.get("draft_response", "")
    context = state.get("context_items", [])
    query = state.get("query", "").lower()
    required_terms = []
    if any(keyword in query for keyword in ["야간", "밤", "night"]):
        required_terms.append("야간")
    if "프리미엄" in query:
        required_terms.append("프리미엄")
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
    special = state.get("special_response")
    if special:
        return {"response": special}
    items = state.get("context_items", [])
    if not items:
        return {"response": "요청 조건에 맞는 정보를 찾지 못했습니다. 다른 조건으로 다시 문의해 주세요."}
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


def create_graph() -> StateGraph[ChatbotState]:
    graph = StateGraph(ChatbotState)
    graph.add_node("ingest", ingest_node)
    graph.add_node("query_analysis", query_analysis_node)
    graph.add_node("general_response", general_response_node)
    graph.add_node("vector_retrieval", vector_retrieval_node)
    graph.add_node("doc_grader", doc_grader_node)
    graph.add_node("draft_response", draft_response_node)
    graph.add_node("self_rag_validation", self_rag_validation_node)
    graph.add_node("corrective_rag", corrective_rag_node)
    graph.add_node("format_response", formatter_node)

    graph.add_edge(START, "ingest")
    graph.add_edge("ingest", "query_analysis")
    graph.add_conditional_edges(
        "query_analysis",
        route_after_query_analysis,
        {"retrieval": "vector_retrieval", "smalltalk": "general_response"},
    )
    graph.add_edge("vector_retrieval", "doc_grader")
    graph.add_conditional_edges(
        "doc_grader",
        route_after_grade,
        {"answer": "draft_response", "fallback": "general_response"},
    )
    graph.add_edge("draft_response", "self_rag_validation")
    graph.add_conditional_edges(
        "self_rag_validation",
        route_after_validation,
        {"correction": "corrective_rag", "format": "format_response"},
    )
    graph.add_edge("corrective_rag", "format_response")
    graph.add_edge("general_response", "format_response")
    graph.add_edge("format_response", END)
    return graph


def build_app():
    return create_graph().compile()


def _graph_to_mermaid(graph: StateGraph[ChatbotState]) -> str:
    lines = [
        "---",
        "config:",
        "  flowchart:",
        "    curve: linear",
        "---",
        "graph TD;",
    ]
    seen_nodes = [START, *sorted(graph.nodes.keys()), END]
    for node in seen_nodes:
        if node == START:
            lines.append('\t__start__([<p>__start__</p>]):::first')
        elif node == END:
            lines.append('\t__end__([<p>__end__</p>]):::last')
        else:
            lines.append(f"\t{node}({node})")

    for start, end in sorted(graph._all_edges):  # type: ignore[attr-defined]
        lines.append(f"\t{start} --> {end};")

    for source, branches in graph.branches.items():
        for branch in branches.values():
            if not branch.ends:
                continue
            for label, target in branch.ends.items():
                lines.append(f"\t{source} -. &nbsp;{label}&nbsp; .-> {target};")

    lines.append("\tclassDef default fill:#f2f0ff,line-height:1.2")
    lines.append("\tclassDef first fill-opacity:0")
    lines.append("\tclassDef last fill:#bfb6fc")
    return "\n".join(lines)


def render_mermaid_diagram(output_path: str | Path | None = None) -> str:
    graph = create_graph()
    diagram = _graph_to_mermaid(graph)
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(diagram, encoding="utf-8")
    return diagram
