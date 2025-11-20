#!/usr/bin/env python3
"""Simple PGVector connectivity smoke test for the Itdaing chatbot."""

from __future__ import annotations

import argparse
import json

from chatbot.config import get_settings
from chatbot.flows.consumer import recommend


def main() -> int:
    parser = argparse.ArgumentParser(description="PGVector connectivity tester")
    parser.add_argument("query", nargs="?", default="광주 플리마켓 추천", help="sample query to send")
    parser.add_argument("--limit", type=int, default=3, help="number of items to fetch")
    args = parser.parse_args()

    settings = get_settings()
    print("[config] PGVECTOR_CONNECTION=", settings.pgvector_connection)
    print("[config] VECTOR_COLLECTION=", settings.vector_collection)

    items = recommend(args.query, limit=args.limit)
    print(f"[result] retrieved {len(items)} items")
    for idx, item in enumerate(items, start=1):
        print(f"\n[{idx}] {item.get('name', '추천 마켓')}")
        print(json.dumps(item, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
