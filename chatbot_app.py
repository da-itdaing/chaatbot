"""Application entrypoints (ASGI + CLI) for the LangGraph chatbot."""
from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence, cast

from dotenv import load_dotenv

from chatbot.app import get_app, run_chatbot  # re-export
from chatbot.graph.state import Role  # re-export

load_dotenv()

# Keep a module-level app reference for legacy ASGI imports
CHATBOT_APP = get_app()

ROLE_MAP = {
	"1": "consumer",
	"2": "seller",
}


def _to_role(value: str) -> Optional[Role]:
	if value in ("consumer", "seller"):
		return cast(Role, value)
	return None


def _safe_input(prompt: str) -> Optional[str]:
	try:
		return input(prompt)
	except EOFError:
		return None


def _prompt_role() -> Optional[Role]:
	print("역할을 선택하세요: [1] 소비자 추천  [2] 판매자 안내  (q 입력 시 종료)")
	while True:
		choice = _safe_input("입력: ")
		if choice is None:
			return None
		lowered = choice.strip().lower()
		if lowered in ("q", "quit", "exit"):
			return None
		if lowered in ROLE_MAP:
			return cast(Role, ROLE_MAP[lowered])
		print("1 또는 2 중에서 선택하거나 q를 입력해 종료할 수 있습니다.")


def run_cli(argv: Optional[Sequence[str]] = None) -> int:
	"""Run the terminal chatbot interface."""
	parser = argparse.ArgumentParser(description="Itdaing LangGraph Chatbot CLI")
	parser.add_argument("--role", choices=["consumer", "seller"], help="사전 지정 역할", default=None)
	args = parser.parse_args(list(argv) if argv is not None else None)

	role: Optional[Role] = cast(Optional[Role], args.role)
	if role is None:
		role = _prompt_role()
		if role is None:
			print("종료합니다.")
			return 0

	print("질문을 입력하세요. 'exit' 또는 'quit' 입력 시 종료됩니다.")
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
		if lowered.startswith("switch"):
			_, _, new_role = query.partition(" ")
			maybe_role = _to_role(new_role.strip())
			if maybe_role:
				role = maybe_role
				print(f"역할이 {role} 모드로 변경되었습니다.")
				continue
			print("switch 명령은 'switch consumer' 또는 'switch seller' 형식으로 입력하세요.")
			continue

		response = run_chatbot(role, query)
		print("\n--- 응답 ---")
		print(response)
		print("--------------\n")

		if role == "consumer":
			hint = "판매자 안내 모드로 전환하려면 'switch seller' 입력"
		else:
			hint = "소비자 추천 모드로 전환하려면 'switch consumer' 입력"
		print(hint)


def main() -> None:
	raise SystemExit(run_cli())


__all__ = ["CHATBOT_APP", "run_chatbot", "Role", "run_cli"]


if __name__ == "__main__":
	try:
		main()
	except KeyboardInterrupt:
		sys.exit("\n사용자에 의해 종료되었습니다.")
