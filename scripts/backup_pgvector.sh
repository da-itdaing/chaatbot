#!/usr/bin/env bash
set -euo pipefail

CONTAINER=${PGVECTOR_CONTAINER:-pgvector-container}
DSN=${PGVECTOR_DSN:-postgresql://langchain:langchain@localhost:5432/langchain}
TMP_PATH=${PGVECTOR_TMP_PATH:-/tmp/pgvector_dump.sql}
OUT_PATH=${1:-backups/pgvector_$(date +%Y%m%d%H%M%S).sql}

mkdir -p "$(dirname "$OUT_PATH")"

echo "[pgvector] 컨테이너 ${CONTAINER} 내부에서 덤프 생성 중..."
docker exec -t "$CONTAINER" pg_dump "$DSN" \
  --table langchain_pg_embedding \
  --table langchain_pg_collection \
  --file "$TMP_PATH"

docker cp "$CONTAINER":"$TMP_PATH" "$OUT_PATH"
docker exec "$CONTAINER" rm "$TMP_PATH"

echo "[pgvector] 백업 완료 → $OUT_PATH"
