# PGVector 컨테이너 & JSON 시드 적재 가이드

`pgvector/pgvector:pg16` 컨테이너에 `markets_seed.json`을 불러와 LangGraph 챗봇이 즉시 사용할 수 있는 임베딩 컬렉션을 구축하는 절차를 설명합니다. 모든 명령은 macOS zsh 기준이지만 Windows PowerShell에서도 동일하게 동작합니다.

## 1. 컨테이너 부팅

```bash
docker run --name pgvector-container \
  -e POSTGRES_USER=langchain \
  -e POSTGRES_PASSWORD=langchain \
  -e POSTGRES_DB=langchain \
  -p 6024:5432 \
  -d pgvector/pgvector:pg16
```

- `docker ps --filter name=pgvector-container` 로 상태 확인
- 포트 충돌 시 `-p <로컬포트>:5432` 값만 바꾸면 됩니다.

## 2. Seed JSON 반입 & 스냅샷

1. 컨테이너에 `/seed` 디렉터리를 만든 후 JSON을 복사합니다.
   ```bash
   docker exec pgvector-container mkdir -p /seed
   docker cp data/markets_seed.json pgvector-container:/seed/markets_seed.json
   ```
2. `seed_snapshots` 테이블 생성 및 JSON 저장 (선택).
   ```bash
   docker exec -it pgvector-container psql -U langchain -d langchain <<'SQL'
   CREATE EXTENSION IF NOT EXISTS vector;
   CREATE TABLE IF NOT EXISTS seed_snapshots (
       id          SERIAL PRIMARY KEY,
       raw         JSONB NOT NULL,
       source_path TEXT    NOT NULL,
       created_at  TIMESTAMPTZ DEFAULT NOW()
   );
   INSERT INTO seed_snapshots (raw, source_path)
   SELECT pg_read_file('/seed/markets_seed.json')::jsonb, '/seed/markets_seed.json'
   ON CONFLICT DO NOTHING;
   SQL
   ```
   `seed_snapshots`는 감사 목적으로만 사용되며, 실제 Retrieval은 PGVector 컬렉션을 조회합니다.

## 3. PGVector 컬렉션 적재 스크립트

Seed JSON을 파싱하고 OpenAI 임베딩을 생성하는 작업은 `python -m chatbot.dataset.market_embedder` (우선 권장) 또는 레거시 호환 스크립트 `scripts/load_pgvector.py`가 담당합니다.

```bash
python -m chatbot.dataset.market_embedder --reset
# 또는 레거시:
python scripts/load_pgvector.py --reset
```

- 필수 환경 변수: `PGVECTOR_CONNECTION`, `OPENAI_API_KEY`, `VECTOR_COLLECTION`
- `--reset`: 기존 컬렉션 삭제 후 재생성 (`market_embedder`는 기본값)
- `--dry-run`/`--keep-existing`: market_embedder 전용 옵션으로 삭제 없이 갱신 여부를 선택

### 내부 동작

1. `chatbot.config.get_settings()`로 환경 값을 로드
2. `chatbot.dataset.vector_docs.build_vector_documents()`가 JSON을 LangChain `Document` 리스트로 변환
3. OpenAI 임베딩 생성 → PGVector `collection_name=VECTOR_COLLECTION`에 업서트
4. 완료 후 총 적재 건수를 출력

## 4. 백업 & 복원

벡터 컬렉션을 보관하려면 `scripts/backup_pgvector.sh`를 사용하세요.

```bash
./scripts/backup_pgvector.sh backups/pgvector_$(date +%Y%m%d%H%M).sql
```

- 옵션: `PGVECTOR_CONTAINER`, `PGVECTOR_DSN`, `PGVECTOR_TMP_PATH`
- 기본으로 `langchain_pg_embedding`, `langchain_pg_collection` 두 테이블만 덤프합니다.
- 복원 시에는 일반 `psql` 또는 `pg_restore`로 해당 SQL을 다시 실행하면 됩니다.

## 5. 운영 체크리스트

- 컨테이너 재기동 시 `load_pgvector.py --reset`으로 임베딩을 다시 적재해야 합니다.
- 새 Seed JSON이 도착하면 `seed_snapshots`에 기록 후 동일 스크립트로 재임베딩하세요.
- 정기 백업을 `backups/` 폴더에 저장하고 Git 추적 대상에서 제외합니다 (`.gitignore` 적용).
- README와 본 문서의 명령은 동일한 값으로 유지되므로 두 문서를 동시에 업데이트해야 합니다.

---

문의는 LangGraph 또는 데이터 파이프라인 담당자에게 `container_setup.md` 섹션 번호와 함께 전달하면 빠르게 처리됩니다.
