"""Dataset loading utilities."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

from ..config import get_settings


def _read_dataset(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Seed data not found at {path}.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and "markets" in payload:
        markets = payload.get("markets")
        if isinstance(markets, list):
            return markets
    raise ValueError("markets_seed.json 형식이 올바르지 않습니다. 최상위에 배열이 있어야 합니다.")


@lru_cache(maxsize=1)
def load_markets_dataset() -> List[Dict[str, Any]]:
    settings = get_settings()
    return _read_dataset(settings.markets_seed_path)


__all__ = ["load_markets_dataset"]
