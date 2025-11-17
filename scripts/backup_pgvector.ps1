# PGVector 컨테이너 백업 스크립트 (Windows PowerShell)
param(
    [string]$OutputPath = ""
)

$CONTAINER = if ($env:PGVECTOR_CONTAINER) { $env:PGVECTOR_CONTAINER } else { "pgvector-container" }
$DSN = if ($env:PGVECTOR_DSN) { $env:PGVECTOR_DSN } else { "postgresql://langchain:langchain@localhost:5432/langchain" }
$TMP_PATH = if ($env:PGVECTOR_TMP_PATH) { $env:PGVECTOR_TMP_PATH } else { "/tmp/pgvector_dump.sql" }

# 출력 경로 기본값 설정
if ([string]::IsNullOrEmpty($OutputPath)) {
    $timestamp = Get-Date -Format "yyyyMMddHHmmss"
    $OutputPath = "backups/pgvector_$timestamp.sql"
}

# 출력 디렉토리 생성
$outputDir = Split-Path -Parent $OutputPath
if (![string]::IsNullOrEmpty($outputDir) -and !(Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
}

Write-Host "[pgvector] 컨테이너 $CONTAINER 내부에서 덤프 생성 중..." -ForegroundColor Cyan

# pg_dump 실행
docker exec -t $CONTAINER pg_dump $DSN `
    --table langchain_pg_embedding `
    --table langchain_pg_collection `
    --file $TMP_PATH

if ($LASTEXITCODE -ne 0) {
    Write-Host "[pgvector] 덤프 생성 실패" -ForegroundColor Red
    exit 1
}

# 덤프 파일 복사
docker cp "${CONTAINER}:${TMP_PATH}" $OutputPath

if ($LASTEXITCODE -ne 0) {
    Write-Host "[pgvector] 파일 복사 실패" -ForegroundColor Red
    exit 1
}

# 임시 파일 삭제
docker exec $CONTAINER rm $TMP_PATH

Write-Host "[pgvector] 백업 완료 → $OutputPath" -ForegroundColor Green
