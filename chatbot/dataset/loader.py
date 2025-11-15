"""Dataset loading utilities."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

from ..config import get_settings


def _read_seed(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Seed data not found at {path}.")
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_seed_dataset() -> Dict[str, Any]:
    settings = get_settings()
    return _read_seed(settings.seed_path)
