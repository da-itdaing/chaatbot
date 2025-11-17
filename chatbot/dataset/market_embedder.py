"""Embedder utilities for the markets seed dataset."""
from __future__ import annotations

import argparse
from typing import Sequence

from langchain_core.documents import Document

from ..retrieval.vector_store import get_vector_store
from .vector_docs import build_market_documents


def _load_documents() -> list[Document]:
    documents = build_market_documents()
    if not documents:
        raise RuntimeError("markets_seed.json에서 문서를 생성하지 못했습니다.")
    return documents


def embed_markets(documents: Sequence[Document] | None = None, reset_collection: bool = True) -> int:
    docs = list(documents) if documents is not None else _load_documents()
    store = get_vector_store()
    if reset_collection:
        store.delete_collection()
    store.create_collection()
    store.add_documents(docs)
    return len(docs)


def cli(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Embed markets_seed data into PGVector.")
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="기존 벡터 컬렉션을 삭제하지 않고 문서를 추가합니다 (권장되지 않음)",
    )
    parser.add_argument("--dry-run", action="store_true", help="임베딩 없이 문서 개수만 확인")
    args = parser.parse_args(list(argv) if argv is not None else None)

    documents = _load_documents()
    count = len(documents)

    if args.dry_run:
        print(f"[dry-run] {count}개 문서를 생성했습니다. PGVector에는 쓰지 않습니다.")
        return 0

    reset_flag = not args.keep_existing
    if reset_flag:
        print("[reset] 기존 컬렉션을 삭제한 뒤 새로 구성합니다.")
    else:
        print("[warn] 기존 컬렉션을 유지합니다. 데이터 스키마 차이로 권장되지 않습니다.")

    print(f"{count}개 문서를 임베딩하여 컬렉션에 적재합니다...")
    embed_markets(documents=documents, reset_collection=reset_flag)
    print("임베딩이 완료되었습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
