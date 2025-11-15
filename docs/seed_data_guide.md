# Seed 데이터 제작 가이드 (Itdaing)

본 문서는 `data/itdaing_seed.json`을 팀원이 이해하고 유지보수할 수 있도록 제작 배경, 구조, 원칙, 자동화 스크립트, 검수 체크리스트를 정리한 안내서입니다.

## 1. 목적과 범위
- 광주 지역 플리마켓 추천/안내 챗봇용 학습·테스트 데이터
- 현실감 있는 셀러/소비자/팝업 정보를 수작업 중심으로 큐레이션
- Guardrails(가드레일)와 엣지 케이스 검증까지 고려

## 2. 데이터 구조 개요
파일: `data/itdaing_seed.json`

- `zones`: 광주 5개 구(남/북/동/서/광산)와 테마 존 정의
- `cells`: 각 존의 세부 셀(위치 슬롯)
- `popups` (143개): 실제 열리는 팝업 부스 정보
  - `popup_id`, `seller_login`, `zone_id`, `cell_id`, `name`, `description`
  - `categories`(주요 카테고리), `styles`(연출 톤), `features`(편의시설)
  - `approval_status`(APPROVED/PENDING/REJECTED), `view_count`, `operating_time`, `event_tags`
- `sellers` (55명): 플리마켓 소상공인 목록
  - `login_id`, `name`, `activity_region`, `specialty`, `intro`
- `consumers` (25명): 페르소나(연령대/MBTI/선호 카테고리/스타일)
- `guardrails`: 주제 이탈·금지 콘텐츠 대응 설정(요약)

## 3. 제작 원칙 (중요 규칙)
1) 팝업명(`popup.name`)은 판매자 상호명과 동일
2) 판매자 전문분야(`seller.specialty`)와 팝업 `categories[0]`는 반드시 일치
   - specialty→category 매핑: fashion/beauty/lifestyle/culture/food
3) `description`은 판매자의 브랜드 아이덴티티와 상품을 구체적으로 반영(수작업 톤앤매너)
4) `operating_time` 형식: `HH:MM-HH:MM` (예: `10:00-20:00`)
5) `features` 값 예: `wheelchair`, `wifi`, `restroom`, `pet`, `parking`
6) `event_tags` 값 예: `workshop`, `family`, `live_music`, `sustainability`, `local_brand`
7) `approval_status` 값: `APPROVED | PENDING | REJECTED` (시나리오 다양성 목적)
8) `activity_region` 값: `gwangju_nam|buk|dong|seo|gwangsan`

## 4. 제작 과정 (히스토리 요약)
- 판매자 15→50명 확장, 소비자 50→25명 축소(핵심 데이터에 집중)
- 팝업 143개를 50명에게 라운드로빈 재배분 및 팝업명=상호명으로 표준화
- 판매자별 전문성에 맞춰 팝업 설명 전면 수작업 리라이트(브랜드 보이스 반영)
- 실제 현장 케이스 반영해 5명 추가(총 55명)
  - `헤어리본공방`(fashion/헤어액세서리)
  - `비즈앤스톤`(fashion/천연석 비즈 공예)
  - `럭키클로버`(lifestyle/네잎클로버·압화)
  - `매직쇼타임`(culture/마술쇼)
  - `타로앤포춘`(culture/타로 리딩)
- 최종 분포: 팝업 143개 / 판매자 55명 → 판매자당 평균 2.6개 팝업

## 5. 자동화 스크립트
> 수작업이 원칙이지만, 대량 정합성/재배분은 스크립트를 보조적으로 사용합니다.

- `scripts/redistribute_popups.py`
  - 기능: 팝업을 판매자에게 라운드로빈으로 재배분, 팝업명=상호명 업데이트
  - 실행:
    ```bash
    python3 scripts/redistribute_popups.py
    ```
- `scripts/fix_popup_names.py`
  - 기능: `seller_login` 기준으로 팝업명을 일괄 갱신
- `scripts/verify_popup_categories.py`
  - 기능: 판매자 `specialty`와 팝업 `categories[0]` 불일치 탐지
  - 실행:
    ```bash
    python3 scripts/verify_popup_categories.py
    ```
- `scripts/add_new_sellers.py`
  - 기능: 신규 판매자(51~55) 추가 및 뒤쪽 팝업 일부 재배분/설명 업데이트
  - 실행:
    ```bash
    python3 scripts/add_new_sellers.py
    ```
- Postgres/PGVector 컨테이너에 JSON 시드를 반입하고 `seed_snapshots` 테이블로 보관하는 절차는 `daitdaing_chatbot_guideline_md/container_setup.md` 참고.

## 6. 수작업 가이드(설명 톤앤매너)
- 문장 톤: 현장감/공감/가벼운 디테일(체험·토크·워크숍·편의시설)
- 브랜드 일치: 셀러 `intro`와 상품군을 자연스럽게 녹임
- 중복 회피: 셀러/팝업 간 어휘를 너무 반복하지 않기(차별화)
- 지역성: 광주 맥락을 과장 없이 반영(시장/골목/시간대 분위기 등)

## 7. 품질 점검 체크리스트
- [ ] 팝업명=판매자명 일치 여부 확인
- [ ] `categories[0]` == `seller.specialty`
- [ ] `operating_time` 형식 유효
- [ ] `features` 값 오탈자 없는지
- [ ] 불필요한 중복/모순 표현 제거
- [ ] 새 판매자(51~55) 관련 팝업 최소 2개 이상 배정 여부
- [ ] 평균 분포(≈2.6개/판매자) 크게 벗어나지 않는지

## 8. 확장 가이드
- 셀러 추가 시:
  1) `sellers`에 신규 레코드 추가
  2) 팝업 일부 재배분(스크립트 or 수작업)
  3) 설명/카테고리/편의시설/태그 정합성 점검
- 카테고리 확장 시:
  - specialty↔category 1:1 원칙 유지 or 명확한 예외 규정 문서화

## 9. FAQ (요약)
- Q. 팝업명은 꼭 셀러명과 같아야 하나요?
  - A. 네. 사용자 인지 일관성을 위해 동일하게 유지합니다.
- Q. categories가 2개 이상이면?
  - A. 첫 번째 값은 `seller.specialty`와 동일, 추가 값은 보조로 활용
- Q. 설명은 자동 생성해도 되나요?
  - A. 기본은 수작업. 대량 업데이트 시 초안 자동 생성 후 수작업 다듬기 권장

---
문서 개선 제안은 PR로 환영합니다. (`docs/seed_data_guide.md`)
