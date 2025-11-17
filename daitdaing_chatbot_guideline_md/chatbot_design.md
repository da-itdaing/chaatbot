# Itdaing LangGraph 챗봇 설계 문서

본 문서는 2025-11-17 00:00 KST 기준으로 운영 중인 소비자 전용 플리마켓 챗봇의 구조와 운영 방법을 정리합니다. Guardrail/Seller 흐름을 제거하고 `markets_seed.json` 단일 데이터셋을 중심으로 LangGraph 실험을 빠르게 반복하는 것이 목표입니다.

## 0. 목표

- LangGraph 상태, Retrieval 계층, 포맷팅 계층을 명확히 분리해 실험 속도를 높임
- 노드 단위로 기능을 추가/제거하며 회귀 테스트(`scripts/run_test_prompts.py`)로 즉시 검증
- 환경 변수(`chatbot/config.py`)와 스크립트(`dataset/market_embedder.py`, `scripts/backup_pgvector.sh`)로 재현 가능한 인프라 제공

## 1. 전체 아키텍처 개요

```
+--------------------------------------------------------------+
|         Application Layer (CLI / Notebook / Future API)      |
+----------------------+---------------------------------------+
| LangGraph StateGraph | Utilities (config, dataset, scripts)  |
+-----------+----------+---------------------------------------+
| Intent    | Consumer Flow | Smalltalk bypass | Self-RAG loop |
+-----------+--------------------------------------------------+
| Retrieval Layer (PGVector, Markets metadata, Synthetic web)  |
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
    config.py              # BaseSettings, OpenAI/PGVector 설정
    dataset/
      loader.py            # markets_seed.json 메모리 캐시
      market_utils.py      # 레코드 정규화 + 점수 계산 헬퍼
      market_embedder.py   # OpenAI 임베딩 → PGVector 적재 CLI
    flows/
      consumer.py          # 방문객 추천 로직 (벡터/폴백 스코어)
    formatting/
      response_builder.py  # 소비자용 Markdown 템플릿
    graph/
      builder.py           # StateGraph 정의 (병렬 Retrieval + Self-RAG)
      state.py             # ChatbotState TypedDict + 병합 헬퍼
    retrieval/
      vector_store.py      # PGVector 래퍼
  scripts/
    load_pgvector.py       # Seed → 벡터 컬렉션 적재 레거시 호환
    backup_pgvector.sh     # 컨테이너 내 임베딩 테이블 백업
    run_test_prompts.py    # LangGraph CLI 자동 실행 + JSON 리포트
```

## 3. StateGraph 노드

| 구분           | 노드                                              | 설명                                                                |
| -------------- | ------------------------------------------------- | ------------------------------------------------------------------- |
| 입력 정규화    | `ingest`                                          | 공백 제거 + 기본 질의 확보                                          |
| 의도/Smalltalk | `intent_router`                                   | 자기소개/Smalltalk 감지, `special_response`/`bypass_retrieval` 세팅 |
| Retrieval 계획 | `retrieval_planner`                               | vector/metadata/web 태스크 목록 생성                                |
| 병렬 검색      | `vector_retrieval`, `metadata_scan`, `web_search` | LangGraph 병렬 실행, `completed_tasks` 업데이트                     |
| 동기화         | `parallel_sync`, `await_parallel`                 | 모든 태스크 완료 여부 판단                                          |
| 초안 생성      | `draft_response`                                  | vector evidence 기반 소비자용 초안 작성                             |
| Self-RAG       | `self_rag_validation`                             | coverage 및 missing facet 평가                                      |
| Corrective-RAG | `corrective_rag`                                  | 부족 facet을 쿼리에 주입한 재검색                                   |
| 포맷팅         | `format_response`                                 | Smalltalk/Correction 여부 반영 후 최종 응답                         |

## 4. 상태 모델 (`chatbot/graph/state.py`)

```python
class ChatbotState(TypedDict, total=False):
    query: str
    special_response: str
    bypass_retrieval: bool
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

`typing_extensions.Annotated`를 사용해 리스트/딕셔너리 병합 정책을 명시했습니다. Guardrail, Seller 필드는 완전히 제거되었습니다.

## 5. Retrieval Layer

- **Vector Retrieval**: `flows.consumer.recommend` → PGVector 우선, 실패 시 markets_seed 폴백 점수(`score_market`) 사용
- **Metadata Scan**: `builder._summarize_market_metadata`가 markets_seed 상위 항목의 위치/속성/편의시설을 샘플링
- **Synthetic Web Search**: `_synthesize_web_updates`가 Self-RAG `missing_facets`를 문자열로 풀어 보조 근거 생성 (향후 Tavily로 교체 예정)
- **Parallel Sync**: `retrieval_tasks` vs `completed_tasks` 비교로 모든 분기가 끝나야 초안 단계로 진입

## 6. Formatting & Smalltalk

- `response_builder.format_consumer`는 추천 카드/체크 리스트/후속 제안으로 구성
- Smalltalk가 감지되면 `special_response`를 즉시 작성 후 Retrieval 단계를 우회
- Self-RAG가 `fail`을 반환하거나 `corrective_rag`가 실행되면 결과 하단에 보충 멘트를 추가해 투명성을 높임

## 7. 스크립트 & 자동화

| 스크립트                             | 목적                                                | 비고                                            |
| ------------------------------------ | --------------------------------------------------- | ----------------------------------------------- |
| `chatbot/dataset/market_embedder.py` | markets_seed.json → OpenAI 임베딩 → PGVector upsert | `--dry-run`, `--keep-existing` 옵션 지원        |
| `scripts/load_pgvector.py`           | 레거시 CLI과 동일한 플로우로 PGVector 적재          | markets_seed 경로만 사용                        |
| `scripts/backup_pgvector.sh`         | 컨테이너 내부 `langchain_pg_*` 테이블 덤프          | Windows PowerShell 버전도 제공                  |
| `scripts/run_test_prompts.py`        | CLI를 자동 호출하고 JSON 리포트 생성                | `results/test_prompts_results_latest.json` 갱신 |

## 8. 테스트 전략

- **Graph smoke**: `scripts/run_test_prompts.py --roles consumer --limit N`
- **데이터 회귀**: markets_seed 수정 후 `market_embedder` + CLI 스팟 테스트 실행
- **여유 과제**: pytest 기반 unit 테스트를 추가해 `score_market`, `_summarize_market_metadata` 등 순수 함수를 검증할 예정

## 9. 운영 및 성능 참고

| 항목           | 현재 전략                     | 후속 액션                                              |
| -------------- | ----------------------------- | ------------------------------------------------------ |
| 임베딩 비용    | `text-embedding-3-small`      | 트래픽 증가 시 Popularity 기반 selective re-embed 검토 |
| 프롬프트 지연  | vector/metadata/web 병렬 실행 | 실제 웹 검색 API 연결 시 timeout 제어 필요             |
| Smalltalk 판별 | 키워드 기반 탐지              | 후속 단계에서 경량 분류 모델 도입 예정                 |
| 관측성         | 터미널 로그 + 수동 JSON 비교  | Prometheus/OTLP collector 연동 계획                    |

## 10. 로드맵

| 단계           | 내용                                               | 산출물                   |
| -------------- | -------------------------------------------------- | ------------------------ |
| Phase 1 (완료) | Consumer-only 전환 + markets_seed 통합             | v2025.11.17 스냅샷       |
| Phase 2        | Tavily/실웹 검색 노드 연결, Self-RAG 임계치 고도화 | 개선된 `web_search` 노드 |
| Phase 3        | FastAPI/ASGI 엔드포인트 노출 + 세션 메모리         | `chatbot_app.py` 재사용  |
| Phase 4        | Pytest + Snapshot 회귀 테스트 도입                 | `tests/` 디렉토리 생성   |

---

질문이나 제안은 섹션 번호와 함께 이슈/PR로 남기면 추적이 쉽습니다.
