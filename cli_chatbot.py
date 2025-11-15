"""Shim to keep the historical CLI entrypoint importable."""
from __future__ import annotations

from chatbot_app import run_cli


def main() -> None:
    run_cli()


if __name__ == "__main__":
    main()
