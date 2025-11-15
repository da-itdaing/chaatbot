"""Seed the PGVector store with Itdaing dataset documents."""
from __future__ import annotations

import argparse
import sys
from typing import Sequence

from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector
from pydantic import SecretStr
from sqlalchemy import create_engine

from chatbot.config import get_settings
from chatbot.dataset.vector_docs import build_vector_documents


def _require(value: str | None, label: str) -> str:
    if value:
        return value
    raise SystemExit(f"환경변수 {label} 설정이 필요합니다.")


def _create_vectorstore(connection: str, collection: str, api_key: str, model: str) -> PGVector:
    embeddings = OpenAIEmbeddings(model=model, api_key=SecretStr(api_key))
    engine = create_engine(connection)
    return PGVector(
        connection=engine,
        collection_name=collection,
        embeddings=embeddings,
        use_jsonb=True,
    )


def load_documents(include_prompts: bool = False) -> Sequence:
    documents, _ = build_vector_documents(include_prompts=include_prompts)
    if not documents:
        raise SystemExit("추출된 문서가 없습니다. seed 데이터나 경로를 확인하세요.")
    return documents


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load Itdaing seed data into PGVector")
    parser.add_argument("--include-prompts", action="store_true", help="테스트 프롬프트도 함께 적재")
    parser.add_argument("--reset", action="store_true", help="기존 컬렉션을 삭제 후 재생성")
    args = parser.parse_args(list(argv) if argv is not None else None)

    settings = get_settings()
    connection = _require(settings.pgvector_connection, "PGVECTOR_CONNECTION")
    api_key = _require(settings.openai_api_key, "OPENAI_API_KEY")
    collection = _require(settings.vector_collection, "VECTOR_COLLECTION")
    model = settings.openai_embedding_model

    vectorstore = _create_vectorstore(connection, collection, api_key, model)

    if args.reset:
        print(f"[reset] 기존 컬렉션 '{collection}'을 삭제합니다.")
        vectorstore.delete_collection()
    # 컬렉션이 없으면 새로 만든다.
    vectorstore.create_collection()

    docs = load_documents(include_prompts=args.include_prompts)
    print(f"{len(docs)}개 문서를 임베딩 후 '{collection}' 컬렉션에 적재합니다...")
    vectorstore.add_documents(list(docs))
    print("적재가 완료되었습니다.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        sys.exit("\n사용자에 의해 중단되었습니다.")
