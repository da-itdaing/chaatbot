"""Convert docs/test_prompt.md into machine-readable JSON."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List, Literal, Optional, TypedDict

ROOT_DIR = Path(__file__).resolve().parent.parent
SOURCE_MD = ROOT_DIR / "docs" / "test_prompt.md"
TARGET_JSON = ROOT_DIR / "data" / "test_prompts.json"

Role = Literal["consumer", "edge"]


class PromptRecord(TypedDict):
    id: str
    role: Role
    section: str
    text: str
    raw: str


def _role_from_heading(heading: str) -> Role:
    lowered = heading.lower()
    if "소비자" in lowered or "consumer" in lowered:
        return "consumer"
    return "edge"


def _normalize_prompt(line: str) -> str:
    value = line.strip().lstrip("*").strip()
    if value.startswith("\"") and value.endswith("\""):
        value = value[1:-1]
    if value.startswith("“") and value.endswith("”"):
        value = value[1:-1]
    return value.strip()


def parse_prompts(markdown: str) -> List[PromptRecord]:
    prompts: List[PromptRecord] = []
    current_role: Optional[Role] = None
    current_section: str = ""
    section_counter: int = 0
    line_counter: int = 0

    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("### "):
            heading = line.lstrip("# ")
            current_role = _role_from_heading(heading)
            current_section = ""
            section_counter = 0
            continue
        if line.startswith("#### "):
            current_section = line.lstrip("# ").strip()
            section_counter = 0
            continue
        if line.startswith("*"):
            section_counter += 1
            line_counter += 1
            text = _normalize_prompt(line)
            prompts.append(
                {
                    "id": f"{(current_role or 'edge')[0].upper()}-{line_counter}",
                    "role": current_role or "edge",
                    "section": current_section or "misc",
                    "text": text,
                    "raw": raw_line.rstrip(),
                }
            )
    return prompts


def main() -> None:
    if not SOURCE_MD.exists():
        raise FileNotFoundError(f"Cannot find {SOURCE_MD}")
    markdown = SOURCE_MD.read_text(encoding="utf-8")
    prompts = parse_prompts(markdown)
    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "source": str(SOURCE_MD.relative_to(ROOT_DIR)),
        "count": len(prompts),
        "prompts": prompts,
    }
    TARGET_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(prompts)} prompts to {TARGET_JSON}")


if __name__ == "__main__":
    main()
