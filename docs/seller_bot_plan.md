# Seller 챗봇 로드맵

이 문서는 `bot_type="SELLER"` 요청을 위한 전용 LangGraph 플로우를 구축하기 위한 단계별 계획입니다.

## 1. 요구사항 정리
- 판매자용 FAQ (부스 신청, 정산, 일정, 필요 서류 등) 수집
- `/api/chat` 에서 SELLER 세션이 생성될 때 별도 태그(`client:seller`) 부여
- 답변은 운영 정책/정적 데이터 + 필요 시 OpenAI 호출을 혼합

## 2. 데이터 및 검색 계층
- `docs/` 또는 별도 S3 버킷에 판매자 문서를 JSON/Markdown으로 정리
- `chatbot/dataset/vector_docs.py`를 재사용해 SELLER 전용 컬렉션 (예: `itdaing_sellers`) 생성
- `generate-chatbot-env.sh`에 `SELLER_VECTOR_COLLECTION`(선택) 추가 고려

## 3. LangGraph 플로우 설계
1. `chatbot/graph/seller_builder.py`
   - Intent Router: 판매자 문의/小talk 구분
   - Retrieval node: SELLER 컬렉션 PGVector → Document list
   - Draft generation: LLM이 공식 톤으로 답변
   - Validation: 필수 필드 포함 여부 확인
2. `chatbot/graph/seller_state.py`로 상태 모델 관리
3. `chatbot/formatting/seller_response.py`에서 Markdown 템플릿 통일

## 4. FastAPI 연동
- `chatbot/api/fastapi_app.py`의 SELLER 분기에서
  - seller 그래프 호출 → answer + supporting docs
  - `items` 필드에는 필요한 서류/링크/담당자 연락처 등 구조화 정보 제공

## 5. QA 및 롤아웃
- 판매자용 테스트 프로토콜 정의 (별도 test_prompts JSON)
- Spring에서 SELLER 세션을 분리 저장해 분석 가능하도록 `bot_type` 필드 활용
- 초기에는 운영팀 내부만 사용 → 피드백 수집 후 확장

문서/데이터가 준비되면 상기 단계를 순서대로 수행하고, 완료 시 본 문서에 결과와 참고 링크를 추가해 주세요.
