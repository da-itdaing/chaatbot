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
        category = _join(item.get("categories", []))
        style = _join(item.get("styles", []))
        features = _join(item.get("features", []))
        highlight = (
            f"{idx}. {item['name']} — {item['zone']} 존 / 셀 {item['cell']}\n"
            f"   · 어울리는 카테고리: {category}\n"
            f"   · 분위기 키워드: {style}\n"
            f"   · 편의시설: {features}\n"
            f"   · 운영 시간: {item.get('operating_time', '상시')}"
        )
        highlights.append(highlight)

    intro = "눈에 띄는 팝업들을 모아봤어요. 분위기를 바꾸고 싶으면 언제든 말씀 주세요!"
    outro = "더 궁금한 지역이나 날짜가 있다면 이어서 도와드릴게요."
    return "\n".join([intro, "", *highlights, "", outro])


def format_seller(items: List[Dict]) -> str:
    if not items:
        return "추천할 존 정보를 찾지 못했습니다. 원하는 판매 품목이나 분위기를 더 알려주시면 찾아볼게요."

    paragraphs: List[str] = []
    for idx, item in enumerate(items[:5], start=1):
        amenities = _join(item.get("features", []))
        paragraphs.append(
            (
                f"{idx}. {item['zone']} 존 ({item['theme']} 테마)\n"
                f"   · 추천 셀: {item.get('suggested_cell', '미정')} — {item.get('cell_notice', '셀 안내 준비 중')}\n"
                f"   · 이용 편의: {amenities}\n"
                f"   · 다음 단계: {item.get('next_step', '온라인 신청서 작성')}"
            )
        )

    intro = "판매자님께 어울릴 것 같은 존을 골라봤어요. 현장 분위기와 편의시설을 함께 확인해보세요."
    outro = "추가 서류 준비나 셀 배정이 필요하면 바로 안내드릴게요."
    return "\n".join([intro, "", *paragraphs, "", outro])
