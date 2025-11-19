"""Application entrypoints (ASGI + CLI) for the LangGraph chatbot."""
from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from dotenv import load_dotenv

from chatbot.app import get_app, run_chatbot  # re-export
from chatbot.graph import builder as graph_builder

load_dotenv()

# Keep a module-level app reference for legacy ASGI imports
CHATBOT_APP = get_app()

def _safe_input(prompt: str) -> Optional[str]:
	try:
		return input(prompt)
	except EOFError:
		return None


def run_cli(argv: Optional[Sequence[str]] = None) -> int:
	"""Run the consumer-focused terminal chatbot interface."""
	parser = argparse.ArgumentParser(description="Itdaing LangGraph Chatbot CLI (consumer mode)")
	args = parser.parse_args(list(argv) if argv is not None else None)
	_ = args  # 현재는 추가 옵션이 없지만 argparse를 유지해 향후 확장 대비

	print("[startup] PGVector 벡터 스토어에 연결 중...")
	try:
		graph_builder.warm_up_vector_backend()
	except Exception as exc:  # pragma: no cover - user-facing error path
		print(f"벡터 스토어 연결에 실패했습니다: {exc}")
		print("도커 컨테이너와 환경 변수를 확인한 뒤 다시 시도해주세요.")
		return 1
	print("[startup] 벡터 스토어 연결 성공. 챗봇이 준비되었습니다!\n")

	print("광주 플리마켓 추천 챗봇입니다. 원하는 분위기나 지역을 물어봐 주세요! 'exit' 입력 시 종료됩니다.")
	while True:
		raw = _safe_input("> ")
		if raw is None:
			print("\n입력이 종료되어 대화를 마칩니다.")
			return 0
		query = raw.strip()
		if not query:
			continue
		lowered = query.lower()
		if lowered in {"exit", "quit"}:
			print("대화를 종료합니다.")
			return 0

		response = run_chatbot(query)
		print("\n--- 응답 ---")
		print(response)
		print("--------------\n")


def main() -> None:
	raise SystemExit(run_cli())


__all__ = ["CHATBOT_APP", "run_chatbot", "run_cli"]


if __name__ == "__main__":
	try:
		main()
	except KeyboardInterrupt:
		sys.exit("\n사용자에 의해 종료되었습니다.")
