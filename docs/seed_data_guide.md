# Markets Seed 데이터 가이드

본 문서는 `data/markets_seed.json` 파일을 유지보수하는 팀원을 위해 제작 배경, 구조, 품질 원칙, 자동화 스크립트, 검수 절차를 정리한 안내서입니다. 현재 챗봇은 소비자 추천 기능만 제공하므로, 이 단일 데이터셋이 Vector 검색과 메타데이터 요약의 기반이 됩니다.

## 1. 목적과 범위

- 광주 지역 팝업/플리마켓 추천 챗봇을 위한 최소 필수 데이터셋
- 소비자 관점의 마켓 정보(이름, 카테고리, 속성, 편의시설, 위치, 평점, 설명)를 구조화
- Guardrail, seller 페르소나 등 과거 레거시 항목은 더 이상 포함하지 않음

## 2. 데이터 구조 개요

파일: `data/markets_seed.json`

최상위는 `markets` 배열이며 각 항목은 아래 필드를 포함합니다.

- `market_id`: 고유 ID (문자열)
- `market_name`: 노출용 이름
- `market_category`: 대표 카테고리 (fashion/beauty/lifestyle/culture/food 등)
- `market_attribute`: 콘셉트/분위기 키워드 배열
- `market_ameni`: 편의시설 키워드 배열 (`wheelchair`, `wifi`, `restroom`, `pet`, `parking` 등)
- `market_location`: `[{city,district,address,zone_id}]` 형식의 위치 배열
- `market_rating`: 0~5 사이 평점(float)
- `market_description`: 2~3문장 설명
- `market_schedule`: 운영 시간 또는 기간 텍스트 (선택)

## 3. 제작 원칙

1. 설명은 소비자 감성에 맞춰 수작업 톤앤매너 유지(체험 포인트, 분위기, 편의성 언급)
2. `market_attribute`와 `market_ameni`는 3~5개 키워드 조합 권장, 중복 금지
3. 위치 정보는 최소 `city`+`district`를 채우고 필요 시 `address`/`zone_id`로 보강
4. `market_rating`은 3.5~4.9 범위를 주로 사용해 현실감 부여
5. 새 항목 추가 시 기존 카테고리 비율을 크게 깨지 않도록 관리
6. 모든 텍스트는 한글 기준 30~120자 내로 압축해 LangGraph 노드가 즉시 활용 가능하도록 유지

## 4. 제작 과정 요약

- 2025-11 기준 레거시 seed 파일에서 소비자 관련 필드만 추출해 markets 전용 구조로 재작성
- 셀러/존/셀/Guardrail 섹션은 완전히 제거하고 각 기록을 단일 오브젝트로 변환
- 편의시설/속성/위치 배열을 정규화하고 `market_utils.py`에서 사용하는 필드명을 맞춤
- PGVector 임베딩과 메타데이터 노드 모두가 동일한 구조를 참조하도록 `market_embedder`/`loader`를 업데이트

## 5. 자동화 스크립트

- `chatbot/dataset/market_embedder.py`: markets_seed.json을 읽어 OpenAI 임베딩 생성 후 PGVector에 적재
- `scripts/export_test_prompts.py`: 데이터에 맞춘 테스트 시나리오를 JSON으로 변환 (간접적으로 markets 구조 검증)
- 컨테이너로 JSON을 반입하고 `seed_snapshots` 테이블에 저장하는 절차는 `daitdaing_chatbot_guideline_md/container_setup.md` 참고

## 6. 수작업 가이드

- **톤**: 체험 디테일을 담되 과도한 마케팅 표현은 지양
- **편의시설**: 실제 방문자가 궁금해할 요소(교통, 주차, 굿즈, 체험 등)를 구체적으로 명시
- **지역성**: 광주 지명과 동네 분위기를 자연스럽게 녹임
- **중복 회피**: 동일 카테고리라도 설명/속성/편의시설 조합을 다르게 구성

## 7. 품질 점검 체크리스트

- [ ] 모든 항목에 `market_id`, `market_name`, `market_category` 존재
- [ ] `market_attribute`/`market_ameni` 배열 길이(최소 2개 이상) 및 오탈자 확인
- [ ] 위치 배열에 적어도 하나의 레코드와 `city` 값 존재
- [ ] 평점 범위 0~5, float 형태 유지
- [ ] 설명은 2문장 이상이며 불필요한 영어 혼용 없음
- [ ] 파일 전체가 UTF-8 JSON (최상위 배열) 형식인지 검증

## 8. 확장 가이드

- 새로운 행사 유형을 추가할 때는 카테고리/속성 사전을 먼저 정의하고 예시 3개 이상 작성
- 시즌성 마켓은 `market_schedule` 필드를 `"3월 둘째 주말"`과 같이 자유 서술형으로 추가해 필터링 근거 제공
- 테스트 프롬프트(`data/test_prompts.json`)와 문서(`docs/test_prompt.md`)에 신규 테마가 반영되었는지 함께 점검

## 9. FAQ

- **Q. 셀러나 존 정보가 필요한가요?**
  - A. 현재 버전에서는 필요 없습니다. 모든 추천 로직이 단일 markets 리스트만 사용합니다.
- **Q. Guardrail 설정은 어디에 두나요?**
  - A. Guardrail 기능은 제거되었습니다. 정책 관련 시나리오는 테스트 프롬프트로만 검증합니다.
- **Q. 자동 생성 문구를 사용해도 되나요?**
  - A. 초안 생성은 가능하나, 실제 반영 전 사람이 톤과 디테일을 다듬어야 합니다.

---

문서 개선 제안은 PR로 환영합니다. (`docs/seed_data_guide.md`)
