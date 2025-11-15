"""Lightweight query parsing helpers."""
from __future__ import annotations

from typing import Dict, List


def find_matches(query: str, items: List[Dict], key: str, value_key: str) -> List[str]:
    lowered = query.lower()
    matches: List[str] = []
    for item in items:
        label = item.get(value_key, "")
        if isinstance(label, str) and label.lower() in lowered:
            matches.append(item.get(key))
    return matches
