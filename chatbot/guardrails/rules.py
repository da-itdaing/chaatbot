"""Simple guardrail rule evaluation."""
from __future__ import annotations

from typing import Dict, List

from ..dataset.loader import load_seed_dataset


class GuardrailResult:
    def __init__(self, triggered: bool, reason: str | None = None, response: str | None = None):
        self.triggered = triggered
        self.reason = reason
        self.response = response


def _lower_list(values: List[str]) -> List[str]:
    return [value.lower() for value in values]


def evaluate(query: str) -> GuardrailResult:
    data = load_seed_dataset()
    guardrails: Dict = data.get("guardrails", {})
    lower_query = query.lower()
    for keyword in _lower_list(guardrails.get("forbidden_keywords", [])):
        if keyword and keyword in lower_query:
            return GuardrailResult(True, f"금지 키워드 발견: {keyword}", "해당 내용은 안내해 드리기 어렵습니다.")
    for topic in _lower_list(guardrails.get("disallowed_topics", [])):
        if topic and topic in lower_query:
            return GuardrailResult(True, f"금지 토픽: {topic}", "요청하신 주제는 지원하지 않습니다.")
    service_area = guardrails.get("service_area", "")
    if "서울" in query and "광주" not in query:
        return GuardrailResult(True, "서비스 지역 외 요청", f"현재 서비스는 {service_area}만 지원합니다.")
    return GuardrailResult(False)
