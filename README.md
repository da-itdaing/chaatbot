# Itdaing Chatbot Playground

LangGraph 기반 플리마켓 챗봇을 로컬에서 실행·검증·문서화하기 위한 기준 가이드입니다. 2025-11-15 02:00 KST 스냅샷을 기준으로 최신 스크립트와 문서를 정리했습니다.

## 1. 환경 준비

### 1.1 필수 도구

- Python 3.10 이상
- Docker Desktop (또는 호환 가능한 컨테이너 런타임)
- OpenAI API Key (임베딩/답변 공통)
- Git + VS Code 권장

### 1.2 가상환경 생성

- **Windows (PowerShell)**
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\activate
  pip install -r requirements.txt
  ```
- **macOS / Linux (zsh/bash)**
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  ```

### 1.3 환경 변수 (.env)

루트 경로에 `.env`를 만들고 아래 값을 채워주세요.

```bash
APP_ENV=dev
OPENAI_API_KEY=sk-...
TAVILY_API_KEY=tvly-...        # 외부 검색 시 사용 (선택)
PGVECTOR_CONNECTION=postgresql+psycopg://langchain:langchain@localhost:6024/langchain
VECTOR_COLLECTION=itdaing_popups
POSTGRES_HOST=localhost
POSTGRES_PORT=6024
POSTGRES_USER=langchain
POSTGRES_PASSWORD=langchain
POSTGRES_DB=langchain
```

- `PGVECTOR_CONNECTION`과 `VECTOR_COLLECTION`은 `scripts/load_pgvector.py` 및 LangGraph Retrieval 노드가 동일하게 사용합니다.
- `dotenv`는 `chatbot_app.py`와 모든 스크립트에서 자동으로 로드되므로 추가 코드 변경이 필요 없습니다.

### 1.4 Dataset

`data/markets_seed.json` 하나만 사용합니다. 광주 지역 플리마켓 행사를 소비자 시점으로 요약한 레코드(이름, 카테고리, 속성, 편의시설, 위치, 평점, 설명)가 포함되어 있으며 모든 파이프라인은 이 파일을 기준으로 동작합니다. 제작·검수 절차는 `docs/seed_data_guide.md`에 정리되어 있습니다.

## 2. PGVector 컨테이너 & 시드 적재

### 2.1 컨테이너 실행

```bash
docker run --name pgvector-container \
	-e POSTGRES_USER=langchain \
	-e POSTGRES_PASSWORD=langchain \
	-e POSTGRES_DB=langchain \
	-p 6024:5432 \
	-d pgvector/pgvector:pg16
```

- 포트 충돌 시 `-p <호스트포트>:5432` 값을 수정하거나 기존 컨테이너를 제거하세요.
- 상태 확인: `docker ps --filter name=pgvector-container` 또는 `docker logs pgvector-container`.

### 2.2 시드 임베딩 적재

`python -m chatbot.dataset.market_embedder`가 OpenAI 임베딩을 생성해 PGVector 컬렉션에 적재합니다. 기본적으로 **기존 컬렉션을 삭제 후 재생성**하므로, 데이터 스키마가 바뀌었을 때 안전하게 교체할 수 있습니다.

```bash
python -m chatbot.dataset.market_embedder            # 삭제 후 재적재 (기본)
python -m chatbot.dataset.market_embedder --dry-run  # 개수만 확인
python -m chatbot.dataset.market_embedder --keep-existing  # 삭제 없이 추가 (권장 X)
```

- `.env`의 `PGVECTOR_CONNECTION`, `VECTOR_COLLECTION`, `OPENAI_API_KEY`가 설정되어 있어야 합니다.
- 기존 `scripts/load_pgvector.py`도 동일한 CLI를 재사용하므로, 레거시 스크립트를 호출해도 동일하게 동작합니다.

### 2.3 컨테이너 백업

- **Windows (PowerShell)**
  ```powershell
  .\scripts\backup_pgvector.ps1 backups\pgvector_latest.sql
  ```
- **macOS / Linux (bash/zsh)**
  ```bash
  ./scripts/backup_pgvector.sh backups/pgvector_latest.sql
  ```
- 기본값: `PGVECTOR_CONTAINER=pgvector-container`, `PGVECTOR_DSN=postgresql://langchain:langchain@localhost:5432/langchain`.
- 덤프는 `langchain_pg_embedding`, `langchain_pg_collection` 테이블만 포함하며, `backups/` 폴더에 저장됩니다.

### 2.4 컨테이너 내부 JSON 적재 흐름

상세 절차와 `seed_snapshots` 테이블 구조는 `daitdaing_chatbot_guideline_md/container_setup.md`에 있습니다. 컨테이너에 `/seed/markets_seed.json`을 복사한 후 `psql` 또는 Python 스크립트로 JSONB 컬럼에 저장하면 `load_pgvector.py`가 해당 스냅샷을 파싱해 컬렉션을 채웁니다.

## 3. CLI 실행 & 상호작용

```bash
python cli_chatbot.py
```

- 실행 즉시 소비자 추천 모드로 시작하며, 필요한 분위기/지역을 바로 질문하면 됩니다.
- `exit`/`quit` 또는 `Ctrl+D`로 종료합니다.
- Smalltalk/자기소개 질문은 `intent_router`에서 감지되어 검색을 우회(`bypass_retrieval=True`)하고, `format_response` 노드에서 친절한 안내 멘트로 응답합니다.

## 4. 자동 테스트 & 리포트

### 4.1 테스트 데이터

`data/test_prompts.json`과 `docs/test_prompt.md`가 동일한 ID 체계를 사용합니다. C-_, S-_, PI-\* 섹션별 커버리지를 유지하세요.

### 4.2 실행 스크립트

```bash
python scripts/run_test_prompts.py --input data/test_prompts.json --output results/manual_run.json
```

- 실행 결과는 `results/test_prompts_results_<timestamp>.json`으로 저장되며 최신 파일은 `results/test_prompts_results_latest.json`에 복제해 추적합니다.
- 각 레코드는 `id / role / section / text / result / error` 필드를 가지며 실패 건수(`failures`)가 요약에 포함됩니다. 현재 챗봇은 소비자 역할만 처리하므로 입력 JSON에서도 해당 케이스만 사용합니다.

### 4.3 활용 팁

- 새 노드나 Intent 라우터/Smalltalk 로직을 수정할 때마다 스크립트를 실행해 회귀 여부를 확인하세요.
- 프롬프트 파일에 여러 섹션이 있더라도 소비자 시나리오만 실행됩니다.

## 5. 문서 & 데이터 레퍼런스

- `docs/seed_data_guide.md`: 시드 데이터 제작 과정
- `docs/test_prompt.md`: 100+ 시나리오 설명
- `daitdaing_chatbot_guideline_md/chatbot_design.md`: LangGraph 모듈 구조 & 상태 정의
- `daitdaing_chatbot_guideline_md/container_setup.md`: 컨테이너/JSON 시드 운용법
- `daitdaing_chatbot_guideline_md/langgraph_parallel_workflow.md`: 병렬 검색 + Self-RAG 노드 설계

## 6. 그래프/엔진 주요 특징

- Intent Router → 병렬 Retrieval(vector/metadata/web) → Self-RAG → Corrective-RAG → Formatter 순서로 구성
- `bypass_retrieval` 플래그로 Smalltalk/시스템 문의는 즉시 응답
- Self-RAG가 `missing_facets`를 찾으면 `corrective_rag`가 쿼리를 보강해 재검색
- 응답 템플릿은 `chatbot/formatting/response_builder.py`에서 관리하며, 소비자 추천에 집중한 Markdown 포맷을 사용합니다.

## 7. 업데이트 로그 (2025-11-15 02:00 KST)

- `scripts/run_test_prompts.py` 추가: test_prompts.json 기반 자동 실행 + JSON 리포트 저장
- Smalltalk 우회 경로 관련 필드(`special_response`, `bypass_retrieval`)가 `ChatbotState`에 명시
- `scripts/load_pgvector.py`, `scripts/backup_pgvector.sh`로 컨테이너 초기화/백업 자동화
- README 및 가이드라인 문서를 Windows 전용 설명에서 macOS/zsh 친화 버전으로 정리
- `results/test_prompts_results_latest.json`으로 최신 회귀 테스트 상태 추적

---

문의나 수정 요청은 관련 문서의 섹션 번호와 함께 등록하면 추적이 수월합니다.
