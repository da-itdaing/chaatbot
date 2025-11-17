"""Utility script to export the LangGraph structure as a Mermaid diagram."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chatbot.graph.builder import render_mermaid_diagram

DEFAULT_OUTPUT = Path("artifacts/graphs/chatbot_query_flow.mmd")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render the chatbot graph to a Mermaid file")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Mermaid file path (default: {DEFAULT_OUTPUT})",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    diagram = render_mermaid_diagram(args.output)
    print(f"Mermaid diagram saved to {args.output}")
    print()
    print(diagram)


if __name__ == "__main__":
    main()
