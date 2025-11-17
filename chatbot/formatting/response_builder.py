"""Response formatting helpers."""
from __future__ import annotations

from typing import Dict, List


def _join(values: List[str], sep: str = ", ") -> str:
    clean = [value for value in values if value]
    return sep.join(clean) if clean else "정보 준비 중"


def format_consumer(items: List[Dict]) -> str:
    if not items:
        return "아직 추천할 팝업을 찾지 못했어요. 조금 더 원하는 분위기를 알려주시면 다시 찾아볼게요."

    highlights: List[str] = []
    for idx, item in enumerate(items[:5], start=1):
        attributes = _join(item.get("attributes", []))
        amenities = _join(item.get("amenities", []))
        rating = item.get("rating")
        rating_label = f"★{rating:.1f}" if isinstance(rating, (int, float)) else "평점 정보 없음"
        highlight = (
            f"{idx}. {item.get('name', '추천 마켓')} — {item.get('category', '플리마켓')} ({rating_label})\n"
            f"   · 위치: {item.get('location', '광주 전역')}\n"
            f"   · 분위기 키워드: {attributes}\n"
            f"   · 편의시설: {amenities}"
        )
        description = item.get("description")
        if description:
            highlight += f"\n   · 한 줄 소개: {description}"
        highlights.append(highlight)

    intro = "눈에 띄는 팝업들을 모아봤어요. 분위기를 바꾸고 싶으면 언제든 말씀 주세요!"
    outro = "더 궁금한 지역이나 날짜가 있다면 이어서 도와드릴게요."
    return "\n".join([intro, "", *highlights, "", outro])


