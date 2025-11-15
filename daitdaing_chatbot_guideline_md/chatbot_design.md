# Itdaing LangGraph 챗봇 설계 문서

본 문서는 2025-11-15 02:00 KST 기준으로 운영 중인 Itdaing 플리마켓 챗봇의 실제 구조와 향후 확장 계획을 함께 기술합니다. LangGraph StateGraph, Guardrail, Retrieval, Formatting 모듈을 분리해 빠른 실험과 회귀 테스트를 지원하는 것이 핵심 목표입니다.

## 0. 목표
- Seed 데이터, LangGraph 상태, 검색 계층, Guardrail, 포맷팅 계층을 명확히 분리
- 노드 단위 확장을 통해 일정/가격/이벤트 등 신규 기능을 빠르게 추가
- `docs/test_prompt.md`와 `data/test_prompts.json`을 기반으로 한 자동 테스트(`scripts/run_test_prompts.py`)를 운영 루틴에 포함
- 환경 변수 기반 설정(`chatbot/config.py`)과 스크립트(`scripts/load_pgvector.py`, `scripts/backup_pgvector.sh`)로 재현 가능한 인프라 제공

## 1. 전체 아키텍처 개요
```
+--------------------------------------------------------------+
|              Application (CLI / Notebook / Future API)       |
+----------------------+---------------------------------------+
| LangGraph StateGraph | Utilities (config, dataset, scripts)  |
+-----------+----------+---------------------------------------+
| Guardrail | Intent   | Consumer Flow | Seller Flow | Smalltalk|
+-----------+----------+---------------------------------------+
| Retrieval Layer (PGVector, Seed metadata, Synthetic web hints)|
+------------------+--------------------+----------------------+
| Dataset Loader   | Formatting layer   | Scripts & Backups    |
+------------------+--------------------+----------------------+
| Infra: Docker PGVector / OpenAI API / dotenv env / CLI       |
+--------------------------------------------------------------+
```

## 2. 현재 모듈 구조
```
project_root/
  chatbot/
    app.py                 # LangGraph 앱 생성 및 run_chatbot 헬퍼
    config.py              # BaseSettings, PGVector/모델 설정
    dataset/
      loader.py            # seed JSON 파싱, 존/셀 요약 메모리 캐시
      vector_docs.py       # PGVector 업서트를 위한 Document 생성
    flows/
      consumer.py          # 방문객 추천 로직
      seller.py            # 셀러 운영 가이드 로직
    formatting/
      response_builder.py  # role별 Markdown 템플릿
    graph/
      builder.py           # StateGraph 정의 (병렬 Retrieval + Self-RAG)
      state.py             # ChatbotState TypedDict + 병합 헬퍼
    guardrails/
      rules.py             # 범위/정책 검사기 (rules.evaluate)
    retrieval/
      query_parser.py      # 존/지역/키워드 매칭 유틸
  scripts/
    load_pgvector.py       # Seed → PGVector 컬렉션 적재
    backup_pgvector.sh     # 컨테이너 내 임베딩 테이블 백업
    run_test_prompts.py    # LangGraph CLI 자동 실행 + JSON 리포트
```
`evaluation/` 디렉토리는 아직 생성되지 않았으며, 테스트는 전용 스크립트(`run_test_prompts.py`)로 수행합니다.

## 3. StateGraph 노드 상세
| 구분 | 노드 | 설명 |
|------|------|------|
| 입력 정규화 | `ingest` | 공백 제거, 기본 역할 결정(소비자 디폴트) |
| Guardrail | `guardrail` | `rules.evaluate`로 범위·정책 위반 판단, 차단 시 즉시 종료 |
| 의도/역할 | `intent_router` | 판매자 키워드/Smalltalk 감지, `special_response`와 `bypass_retrieval` 세팅 |
| Retrieval 계획 | `retrieval_planner` | 벡터/메타/웹 태스크 목록 생성, smalltalk 시 빈 목록 |
| 병렬 검색 | `vector_retrieval`, `metadata_scan`, `web_search` | LangGraph가 병렬 실행, 완료 시 `completed_tasks` 갱신 |
| 동기화 | `parallel_sync`, `await_parallel` | 모든 태스크 종료 여부 확인 후 초안 단계로 이동 |
| 초안 생성 | `draft_response` | role별 템플릿 적용, special_response 우선 |
| Self-RAG | `self_rag_validation` | coverage/missing facet 계산, 부족 시 `needs_correction=True` |
| Corrective-RAG | `corrective_rag` | 부족 facet을 쿼리에 재주입해 재검색 |
| 포맷팅 | `format_response` | Guardrail/Smalltalk/Correction 결과를 합쳐 최종 문자열 생성 |

## 4. 상태 모델 (`chatbot/graph/state.py`)
```python
class ChatbotState(TypedDict, total=False):
    role: Literal["consumer", "seller"]
    query: str
    special_response: str          # Smalltalk·자기소개 응답
    bypass_retrieval: bool         # true일 경우 검색 노드 비활성화
    guardrail_triggered: bool
    guardrail_reason: str
    retrieval_tasks: List[str]
    completed_tasks: Annotated[List[str], extend_unique]
    evidence: Annotated[Dict[str, Any], merge_dicts]
    insights: Annotated[Dict[str, Any], merge_dicts]
    context_items: List[Dict[str, Any]]
    draft_response: str
    validation: Dict[str, Any]
    needs_correction: bool
    parallel_ready: bool
    response: str
```
TypedDict + `typing_extensions.Annotated`를 사용해 LangGraph 병합 정책을 정의했습니다. Guardrail, Retrieval, Self-RAG 모두 상태 객체에 필요한 필드만 추가하며, 나머지는 LangGraph가 자동 병합합니다.

## 5. Guardrail 및 Intent 처리
- `chatbot/guardrails/rules.py`는 광주 외 지역 요청, 시스템 프롬프트 노출, 위험 소재 등을 템플릿 기반으로 차단합니다.
- Guardrail이 차단을 반환하면 `format_response` 노드에서 별도 로직 없이 즉시 응답을 종료합니다.
- `intent_router`는 Smalltalk 키워드를 탐지해 `special_response`를 준비하고, `insights.intent`에 역할/확신도를 기록합니다.

## 6. Retrieval Layer
- **Vector Retrieval**: `flows.consumer.recommend` / `flows.seller.guide`가 동일한 `get_settings().max_results` 한도를 사용합니다. PGVector는 `settings.pgvector_connection`, `VECTOR_COLLECTION` 환경 변수로 지정합니다.
- **Metadata Scan**: `dataset.loader.load_seed_dataset()`을 사용해 존별 승인/대기 현황을 빠르게 요약합니다.
- **Synthetic Web Search**: 실제 API 대신 `_synthesize_web_updates`가 `missing_facets`를 참고해 보조 문장을 생성합니다. 향후 Tavily/OpenAPI 연결 시 이 노드를 대체할 예정입니다.
- **Parallel Sync**: `retrieval_tasks`와 `completed_tasks`를 비교하여 모든 분기가 끝나야 초안을 작성합니다.

## 7. 응답 포맷팅 (`chatbot/formatting/response_builder.py`)
- 소비자는 추천 카드 + 체크리스트 + 후속 제안으로 구성됩니다.
- 판매자는 존/셀 상황, 준비물, 경쟁도 요약 순으로 안내합니다.
- Self-RAG validation이 `fail`이거나 `corrective_rag`가 실행되면 하단에 보충 안내 문장을 추가해 투명성을 높입니다.

## 8. 스크립트 & 자동화
| 스크립트 | 목적 | 비고 |
|----------|------|------|
| `scripts/load_pgvector.py` | Seed JSON을 Document로 변환 후 PGVector 컬렉션에 upsert | `--reset`, `--include-prompts` 옵션 지원 |
| `scripts/backup_pgvector.sh` | 컨테이너 내부 임베딩 테이블 백업 | `PGVECTOR_CONTAINER`, `PGVECTOR_DSN` 환경 변수로 커스터마이즈 |
| `scripts/run_test_prompts.py` | LangGraph CLI를 자동 호출하고 JSON 리포트 생성 | `results/test_prompts_results_<timestamp>.json` 출력 |

자동 테스트 결과는 `results/test_prompts_results_latest.json` 링크로 최신 상태를 추적합니다.

## 9. 테스트 전략
### 9.1 범주
- **Unit**: `retrieval.query_parser.find_matches`, Guardrail evaluator 등 순수 함수 검증 (pytest 준비 중)
- **Graph smoke**: `scripts/run_test_prompts.py`가 모든 역할/섹션을 돌며 응답/에러를 기록
- **Regression**: Guardrail(범위 이탈), Smalltalk, role switch 등 핵심 시나리오를 매 실행마다 비교

### 9.2 실행
```bash
python scripts/run_test_prompts.py --roles consumer seller --limit 50
```
- 출력 JSON에는 `failures`와 각 프롬프트의 `error` 필드가 포함되어 추세를 곧바로 확인할 수 있습니다.
- CI 통합 시 `failures > 0`이면 실패 처리하도록 구성할 계획입니다.

## 10. 운영 및 성능 고려
| 항목 | 현재 전략 | 후속 액션 |
|------|-----------|-----------|
| 임베딩 비용 | `text-embedding-3-small` 고정 | Popularity 기반 selective re-embed |
| 프롬프트 지연 | 벡터/메타/웹 병렬 실행 | 실제 웹 검색 API 연결 후 timeout 제어 |
| Smalltalk 비율 | `SMALLTALK_KEYWORDS`로 탐지 | NLP 분류기 도입 검토 |
| 관측성 | 터미널 로그 기반 | Prometheus/OTLP collector 연동 예정 |

## 11. 로드맵
| 단계 | 내용 | 산출물 |
|------|------|--------|
| Phase 1 (완료) | LangGraph 병렬 그래프 + Smalltalk bypass + 스크립트 3종 정비 | v2025.11.15 스냅샷 |
| Phase 2 | Tavily/실 웹 검색 노드 연결, Seller zone 추천 고도화 | `web_search` 대체 구현 |
| Phase 3 | FastAPI/ASGI 엔드포인트 노출, 세션 메모리 저장 | `CHATBOT_APP` 재사용 |
| Phase 4 | Pytest + Snapshot 기반 Regression 도입 | `tests/` 디렉토리 생성 |

## 12. 향후 개선 아이디어
- Retriever re-ranking: metadata score와 cosine score를 가중 결합 후 Self-RAG 임계치 상향
- Schedule/Price 노드 추가: `flows.schedule`, `flows.pricing` 모듈을 별도로 두고 필요 시 병렬 태스크에 포함
- Structured output 모드: CLI 외 REST/Slack 연동을 대비해 JSON 포맷 옵션 추가
- Metrics: Guardrail 차단 사유, Corrective-RAG 사용률을 Prometheus gauge로 노출

---
질문이나 제안은 섹션 번호와 함께 이슈/PR로 남기면 추적이 쉽습니다.
