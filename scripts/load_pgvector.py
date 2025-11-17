"""Legacy entrypoint that now delegates to the market embedder CLI."""
from __future__ import annotations

import sys

from chatbot.dataset.market_embedder import cli as embed_cli


def main() -> int:
    print("[info] load_pgvector.py는 chatbot.dataset.market_embedder CLI로 위임되었습니다.")
    return embed_cli()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        sys.exit("\n사용자에 의해 중단되었습니다.")
