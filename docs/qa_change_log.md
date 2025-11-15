# QA Change Log

## 2025-11-14: Popup 카테고리 정합성 보정
- 의도: `scripts/verify_popup_categories.py` 실행 시 143개 중 103개 불일치 발견 → 판매자 specialty와 팝업 1차 카테고리 불일치
- 조치:
  - `scripts/fix_popup_categories.py` 작성 → specialty를 1순위로 강제하고 기존 카테고리는 중복 제거 후 후순위 배치
  - 실행 명령:
    ```bash
    python scripts/fix_popup_categories.py
    python scripts/verify_popup_categories.py
    ```
  - 결과: `verify_popup_categories.py` 재실행 시 0개 불일치
- 백업: `data/itdaing_seed.json.bak` 자동 생성
- 후속: CI에 카테고리 검증 스크립트 포함 예정
