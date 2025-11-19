"""Graph builder translated from the bot4cu notebook flow."""
from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Dict, List, Literal, cast

from langchain_classic import hub
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import PGVector
from langgraph.graph import END, START, StateGraph

from pydantic import BaseModel, Field

from .state import AgentState


DEFAULT_DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "itdaing_seed.json"
DEFAULT_CONNECTION_STRING = "postgresql+psycopg2://langchain:langchain@localhost:6024/langchain"
DEFAULT_COLLECTION_NAME = "itdaing_market"


def load_markets_json(path: str | Path = DEFAULT_DATA_PATH) -> List[Dict[str, Any]]:
    """Load raw market entries from JSON."""

    path = Path(path)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def markets_to_docs(markets: Iterable[Dict[str, Any]]) -> List[Document]:
    """Transform market dictionaries into LangChain documents."""

    docs: List[Document] = []
    for market in markets:
        locations = market.get("market_location", []) or []
        first_location = locations[0] if locations else {}
        attributes = market.get("market_attribute", []) or []
        amenities = market.get("market_ameni", []) or []

        text_block = (
            f"[마켓 정보]\n"
            f"이름: {market.get('market_name', '')}\n"
            f"카테고리: {market.get('market_category', '')}\n"
            f"분위기: {', '.join(attributes)}\n"
            f"편의시설: {', '.join(amenities)}\n"
            f"주소: {first_location.get('address', '')}\n"
            f"거리(km): {first_location.get('distance_km', '')}\n"
            f"존 ID: {first_location.get('zone_id', '')}\n"
            "\n"
            f"[상세 설명]\n{market.get('market_description', '')}"
        )

        metadata = {
            "market_id": market.get("market_id"),
            "market_name": market.get("market_name", ""),
            "market_category": market.get("market_category", ""),
            "market_attribute": attributes,
            "market_ameni": amenities,
            "address": first_location.get("address", ""),
            "distance_km": first_location.get("distance_km"),
            "zone_id": first_location.get("zone_id", ""),
        }

        docs.append(Document(page_content=text_block, metadata=metadata))
    return docs


def split_documents(
    docs: Iterable[Document],
    *,
    chunk_size: int = 700,
    chunk_overlap: int = 100,
) -> List[Document]:
    """Create overlapping chunks ready for vector storage."""

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""],
    )
    return splitter.split_documents(list(docs))


def build_vectorstore(
    documents: Iterable[Document],
    *,
    connection_string: str = DEFAULT_CONNECTION_STRING,
    collection_name: str = DEFAULT_COLLECTION_NAME,
) -> PGVector:
    """Create or overwrite a PGVector collection from documents."""

    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
    return PGVector.from_documents(
        documents=list(documents),
        embedding=embeddings,
        connection_string=connection_string,
        collection_name=collection_name,
    )


def connect_vectorstore(
    *,
    connection_string: str = DEFAULT_CONNECTION_STRING,
    collection_name: str = DEFAULT_COLLECTION_NAME,
) -> PGVector:
    """Connect to an existing PGVector collection."""

    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
    return PGVector(
        connection_string=connection_string,
        embedding_function=embeddings,
        collection_name=collection_name,
    )


def ensure_pgvector_schema(
    *,
    connection_string: str = "postgresql://langchain:langchain@localhost:6024/langchain",
) -> None:
    """Ensure the embedding table has the columns expected by LangChain."""

    import psycopg

    dsn = connection_string.replace("postgresql+psycopg2://", "postgresql://")
    ddl_statements = [
        "CREATE EXTENSION IF NOT EXISTS pgcrypto",
        "ALTER TABLE langchain_pg_embedding ADD COLUMN IF NOT EXISTS custom_id TEXT",
        "ALTER TABLE langchain_pg_embedding ADD COLUMN IF NOT EXISTS uuid UUID DEFAULT gen_random_uuid()",
        "CREATE INDEX IF NOT EXISTS idx_langchain_pg_embedding_uuid ON langchain_pg_embedding (uuid)",
    ]

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            for ddl in ddl_statements:
                cur.execute(ddl)


_retriever = None


def get_retriever(k: int = 3):
    """Lazy-load the PGVector retriever used by the graph."""

    from langchain_core.vectorstores import VectorStoreRetriever

    global _retriever
    if _retriever is None:
        vectorstore = connect_vectorstore()
        _retriever = vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": k},
        )
    assert isinstance(_retriever, VectorStoreRetriever)
    return _retriever


def warm_up_vector_backend(k: int = 3) -> None:
    """Eagerly initialize the PGVector retriever to validate connectivity."""

    get_retriever(k)


class RouteDecision(BaseModel):
    target: Literal["rag_answer", "general_answer"]


router_system_prompt = """
You are an expert router that decides whether a user's question should be answered using
the vector store (rag_answer) or a general LLM response (general_answer).

The vector store contains detailed information about flea markets and popup markets in
광주광역시, including descriptions, locations, categories, attributes, schedules, and
additional metadata.

If the user's question can be satisfied by recommending markets in 광주광역시, return
"rag_answer". This includes cases where the user hints at wanting recommendations even
without explicit keywords. If the request is unrelated to markets, targets another city,
or appears malicious (e.g. unrealistic computation requests), return "general_answer".

Respond with only one token: "rag_answer" or "general_answer".
"""

router_prompt = ChatPromptTemplate.from_messages([
    ("system", router_system_prompt),
    ("user", "{query}"),
])
router_llm = ChatOpenAI(model="gpt-4o-mini")
structured_router_llm = router_llm.with_structured_output(RouteDecision)

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
doc_relevance_prompt = hub.pull("langchain-ai/rag-document-relevance")
generate_prompt = hub.pull("rlm/rag-prompt")
generate_llm = ChatOpenAI(model="gpt-4o", max_completion_tokens=500)

hallucination_prompt = PromptTemplate.from_template(
    """
You are a teacher tasked with evaluating whether a student's answer is based on documents.
Given documents, which are market information, and a student's answer;
if the answer is grounded in the documents respond with "not hallucinated" otherwise
respond with "hallucinated".

documents: {documents}
student_answer: {student_answer}
"""
)
hallucination_llm = ChatOpenAI(model="gpt-4o", temperature=0)

basic_system_prompt = """
당신은 간단한 응답용 챗봇입니다.

질문이 다음에 해당하면 한 문장으로 "서비스와 관련이 없는 질문입니다"라고 답하세요.
1) 광주광역시 외의 지역 마켓 추천 요청
2) 비현실적인 계산이나 대량 나열 등 서버 공격 의도가 있는 요청
그 외에는 간단한 회신을 제공합니다. 답변은 한 문장을 절대 초과하지 마세요.
"""

basic_prompt = ChatPromptTemplate.from_messages([
    ("system", basic_system_prompt),
    ("user", "{query}"),
])
basic_llm = ChatOpenAI(model="gpt-4o-mini", max_completion_tokens=50)

rewrite_prompt = PromptTemplate.from_template(
    """
마켓 추천을 요청한 사용자의 질문을 더 명확하게 만들도록 재작성해 주세요.
질문: {query}
"""
)


def router(state: AgentState) -> Literal["rag_answer", "general_answer"]:
    query = state.get("query", "")
    result = (router_prompt | structured_router_llm).invoke({"query": query})
    decision = cast(RouteDecision, result)
    return decision.target


def retrieve(state: AgentState) -> AgentState:
    query = state.get("query", "")
    docs = get_retriever().invoke(query)
    return {"context": docs}


def check_doc_relevance(state: AgentState) -> Literal["relevant", "irrelevant"]:
    query = state.get("query", "")
    context = state.get("context", [])
    documents = "\n\n".join(doc.page_content for doc in context)
    response = (doc_relevance_prompt | llm).invoke({"question": query, "documents": documents})
    score = response.get("Score") if isinstance(response, dict) else None
    return "relevant" if score == 1 else "irrelevant"


def generate(state: AgentState) -> AgentState:
    context = state.get("context", [])
    query = state.get("query", "")
    documents = "\n\n".join(doc.page_content for doc in context)
    response = (generate_prompt | generate_llm).invoke({"question": query, "context": documents})
    return {"answer": response.content}


def check_hallucination(state: AgentState) -> Literal["hallucinated", "not hallucinated"]:
    answer = state.get("answer", "")
    docs = [doc.page_content for doc in state.get("context", [])]
    result = (hallucination_prompt | hallucination_llm | StrOutputParser()).invoke(
        {"student_answer": answer, "documents": docs}
    )
    normalized = str(result).strip().lower()
    return "not hallucinated" if "not hallucinated" in normalized else "hallucinated"


def basic_generate(state: AgentState) -> AgentState:
    query = state.get("query", "")
    reply = (basic_prompt | basic_llm | StrOutputParser()).invoke({"query": query})
    return {"answer": reply, "context": []}


def rewrite(state: AgentState) -> AgentState:
    query = state.get("query", "")
    rewritten = (rewrite_prompt | llm | StrOutputParser()).invoke({"query": query})
    return {"query": rewritten, "context": []}


def finalize_response(state: AgentState) -> AgentState:
    """Move the working answer into the response slot for downstream consumers."""

    return {
        "response": state.get("answer", ""),
        "context": state.get("context", []),
    }


def create_graph() -> StateGraph[AgentState]:
    graph = StateGraph(AgentState)
    graph.add_node("retrieve", retrieve)
    graph.add_node("generate", generate)
    graph.add_node("rewrite", rewrite)
    graph.add_node("basic_generate", basic_generate)
    graph.add_node("finalize", finalize_response)

    graph.add_conditional_edges(
        START,
        router,
        {"rag_answer": "retrieve", "general_answer": "basic_generate"},
    )
    graph.add_conditional_edges(
        "retrieve",
        check_doc_relevance,
        {"relevant": "generate", "irrelevant": "rewrite"},
    )
    graph.add_conditional_edges(
        "generate",
        check_hallucination,
        {"not hallucinated": "finalize", "hallucinated": "rewrite"},
    )
    graph.add_edge("rewrite", "retrieve")
    graph.add_edge("basic_generate", "finalize")
    graph.add_edge("finalize", END)
    return graph


def build_app():
    return create_graph().compile()


TRACE_FIELDS = (
    "query",
    "context",
    "answer",
)


def _summarize_state(update: Dict[str, Any] | None) -> Dict[str, Any] | None:
    if not update:
        return None
    summary: Dict[str, Any] = {}
    for field in TRACE_FIELDS:
        if field not in update:
            continue
        value = update[field]
        if field == "context":
            summary["context_items"] = len(value) if isinstance(value, list) else value
        else:
            summary[field] = value
    return summary or None


def run_graph_with_trace(graph, initial_state: AgentState) -> None:
    """Utility helper emulating the notebook trace output."""

    from pprint import pprint

    print("=== graph trace start ===")
    for step, event in enumerate(graph.stream(initial_state, stream_mode="values"), start=1):
        for node_name, node_update in event.items():
            if node_name == "__end__":
                continue
            print(f"[step {step}] node = {node_name}")
            summary = _summarize_state(node_update)
            if summary:
                pprint(summary)
            else:
                print("  (no state changes)")
    print("=== graph trace end ===")
