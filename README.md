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

### 1.4 Seed 데이터
`data/itdaing_seed.json`에는 55명의 판매자, 143개의 팝업, 25명의 소비자 페르소나, 광주 5개 구의 존/셀 정보가 포함되어 있습니다. 생성·검수 절차는 `docs/seed_data_guide.md`에 정리되어 있습니다.

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
`scripts/load_pgvector.py`는 OpenAI 임베딩을 생성해 PGVector 컬렉션에 적재합니다.
```bash
python scripts/load_pgvector.py --reset         # 기존 컬렉션 삭제 후 재생성
python scripts/load_pgvector.py --include-prompts
```
- `.env`의 연결 정보와 `VECTOR_COLLECTION`이 설정되어 있어야 합니다.
- `--include-prompts` 옵션은 `data/test_prompts.json`에 포함된 검증 문장을 같이 임베딩합니다.

### 2.3 컨테이너 백업
macOS/zsh 기준 예시:
```bash
./scripts/backup_pgvector.sh backups/pgvector_latest.sql
```
- 기본값: `PGVECTOR_CONTAINER=pgvector-container`, `PGVECTOR_DSN=postgresql://langchain:langchain@localhost:5432/langchain`.
- 덤프는 `langchain_pg_embedding`, `langchain_pg_collection` 테이블만 포함하며, `backups/` 폴더에 저장됩니다.

### 2.4 컨테이너 내부 JSON 적재 흐름
상세 절차와 `seed_snapshots` 테이블 구조는 `daitdaing_chatbot_guideline_md/container_setup.md`에 있습니다. 컨테이너에 `/seed/itdaing_seed.json`을 복사한 후 `psql` 또는 Python 스크립트로 JSONB 컬럼에 저장한 뒤, `load_pgvector.py`가 해당 스냅샷을 파싱해 컬렉션을 채우는 구조입니다.

## 3. CLI 실행 & 상호작용
```bash
python cli_chatbot.py
```
- 시작 시 역할 선택: `[1] 소비자 추천`, `[2] 판매자 안내`, `q` 종료.
- 대화 중 `switch seller`, `switch consumer`로 즉시 역할 전환 가능.
- Smalltalk/자기소개 질문은 `intent_router`에서 감지되어 검색을 우회(`bypass_retrieval=True`)하고, `format_response` 노드에서 친절한 안내 멘트로 응답합니다.
- Guardrail이 범위 외 요청을 감지하면 즉시 차단 사유와 함께 응답을 마칩니다.

## 4. 자동 테스트 & 리포트
### 4.1 테스트 데이터
`data/test_prompts.json`과 `docs/test_prompt.md`가 동일한 ID 체계를 사용합니다. C-*, S-*, PI-* 섹션별 커버리지를 유지하세요.

### 4.2 실행 스크립트
```bash
python scripts/run_test_prompts.py --roles consumer seller --limit 40
python scripts/run_test_prompts.py --input data/test_prompts.json --output results/manual_run.json
```
- 실행 결과는 `results/test_prompts_results_<timestamp>.json`으로 저장되며 최신 파일은 `results/test_prompts_results_latest.json`에 복제해 추적합니다.
- 각 레코드는 `id / role / section / text / result / error` 필드를 가지며 실패 건수(`failures`)가 요약에 포함됩니다.

### 4.3 활용 팁
- 새 노드나 Guardrail을 수정할 때마다 스크립트를 실행해 회귀 여부를 확인하세요.
- `--roles seller` 같은 필터로 특정 유즈케이스만 빠르게 검증할 수 있습니다.

## 5. 문서 & 데이터 레퍼런스
- `docs/seed_data_guide.md`: 시드 데이터 제작 과정
- `docs/test_prompt.md`: 100+ 시나리오 설명
- `daitdaing_chatbot_guideline_md/chatbot_design.md`: LangGraph 모듈 구조 & 상태 정의
- `daitdaing_chatbot_guideline_md/container_setup.md`: 컨테이너/JSON 시드 운용법
- `daitdaing_chatbot_guideline_md/langgraph_parallel_workflow.md`: 병렬 검색 + Self-RAG 노드 설계

## 6. 그래프/엔진 주요 특징
- Guardrail → Intent Router → 병렬 Retrieval(vector/metadata/web) → Self-RAG → Corrective-RAG → Formatter 순서로 구성
- `bypass_retrieval` 플래그로 Smalltalk/시스템 문의는 즉시 응답
- Self-RAG가 `missing_facets`를 찾으면 `corrective_rag`가 쿼리를 보강해 재검색
- Role별 응답 템플릿은 `chatbot/formatting/response_builder.py`에서 관리 (추천/셀러 안내 모두 Markdown 포맷)

## 7. 업데이트 로그 (2025-11-15 02:00 KST)
- `scripts/run_test_prompts.py` 추가: test_prompts.json 기반 자동 실행 + JSON 리포트 저장
- Smalltalk 우회 경로 및 Guardrail 사유가 `ChatbotState`에 명시(`special_response`, `bypass_retrieval`)
- `scripts/load_pgvector.py`, `scripts/backup_pgvector.sh`로 컨테이너 초기화/백업 자동화
- README 및 가이드라인 문서를 Windows 전용 설명에서 macOS/zsh 친화 버전으로 정리
- `results/test_prompts_results_latest.json`으로 최신 회귀 테스트 상태 추적

---
문의나 수정 요청은 관련 문서의 섹션 번호와 함께 등록하면 추적이 수월합니다.
