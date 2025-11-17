#!/usr/bin/env python
"""Run stored test prompts against the chatbot and capture results."""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence

from dotenv import load_dotenv

from chatbot.app import run_chatbot

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT_DIR / "data" / "test_prompts.json"
DEFAULT_RESULTS_DIR = ROOT_DIR / "results"


def _load_prompts(path: Path) -> Sequence[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Prompt 파일을 찾을 수 없습니다: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    prompts = payload.get("prompts", [])
    if not prompts:
        raise RuntimeError("prompts 배열이 비어 있습니다.")
    return prompts


def _iter_consumer_records(prompts: Sequence[dict]):
    for prompt in prompts:
        role = (prompt.get("role") or "consumer").lower()
        if role != "consumer":
            continue
        yield prompt


def _default_output_path(results_dir: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return results_dir / f"test_prompts_results_{timestamp}.json"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run stored test prompts via the chatbot")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="프롬프트 JSON 경로")
    parser.add_argument("--output", type=Path, help="결과 JSON 출력 경로")
    parser.add_argument("--limit", type=int, default=0, help="실행할 최대 프롬프트 수 (0=전체)")
    args = parser.parse_args(list(argv) if argv is not None else None)

    load_dotenv()

    prompts = _load_prompts(args.input)
    selected = list(_iter_consumer_records(prompts))
    if args.limit and args.limit > 0:
        selected = selected[: args.limit]

    if not selected:
        raise SystemExit("선택된 역할에 해당하는 프롬프트가 없습니다.")

    results_dir = args.output.parent if args.output else DEFAULT_RESULTS_DIR
    results_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output or _default_output_path(results_dir)

    records = []
    failures = 0
    for record in selected:
        prompt_id = record.get("id")
        role = "consumer"
        text = record.get("text", "")
        error: str | None = None
        response: str | None = None
        try:
            response = run_chatbot(text)
        except Exception as exc:  # pragma: no cover - diagnostic only
            error = str(exc)
            failures += 1
        records.append(
            {
                "id": prompt_id,
                "role": role,
                "section": record.get("section"),
                "text": text,
                "result": response,
                "error": error,
            }
        )

    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "input_file": str(args.input.relative_to(ROOT_DIR)) if args.input.is_relative_to(ROOT_DIR) else str(args.input),
        "count": len(records),
        "roles": ["consumer"],
        "failures": failures,
        "results": records,
    }
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(records)} responses to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
