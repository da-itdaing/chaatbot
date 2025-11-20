# Chatbot API 운영 가이드

이 문서는 `daitdaing-chatbot` 레포(서버 경로 `/home/ubuntu/chaatbot`)에서 FastAPI 기반 챗봇 서비스를 운영하기 위한 실무 지침을 정리합니다.

---

## 1. FastAPI 엔드포인트 요약

- 실행 모듈: `chatbot.api.fastapi_app:app`
- 기본 포트: `9000`
- 엔드포인트
  - `GET /health` → `{ "status": "ok" }`
  - `POST /chat`
    ```json
    {
      "bot_type": "CONSUMER",
      "user_id": "12345",
      "session_id": "sess-20241120-001",
      "message": "광주 북구 쪽 팝업 추천해줘",
      "history": [ { "role": "user", "content": "이전 메시지" } ],
      "metadata": {
        "roles": ["CONSUMER"],
        "client": "web",
        "locale": "ko-KR",
        "ip": "10.0.0.12"
      },
      "limit": 5
    }
    ```
  - 응답 필드: `answer`, `items[]`, `meta{source, model, latency_ms, trace_id, extra}`
- 로컬 테스트:
  ```bash
  uvicorn chatbot.api.fastapi_app:app --host 0.0.0.0 --port 9000 --reload
  curl -s http://localhost:9000/chat \
    -H 'Content-Type: application/json' \
    -d '{"bot_type":"CONSUMER","user_id":"test","session_id":"sess-1","message":"광주 팝업 추천"}' | jq .
  ```

## 2. PGVector (RDS) 연결 및 스모크 테스트

1. 환경 변수 생성
   ```bash
   cd /home/ubuntu/chaatbot
   AWS_DEFAULT_REGION=ap-northeast-2 ./scripts/generate-chatbot-env.sh
   source chatbot.env  # 또는 systemd EnvironmentFile 사용
   ```
2. RDS에 `vector` 확장 설치 (최초 1회):
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
3. markets_seed.json 임베딩 적재:
   ```bash
   python -m chatbot.dataset.market_embedder --reset
   # 또는
   python scripts/load_pgvector.py --reset
   ```
4. 스모크 테스트:
   ```bash
   ./scripts/vector_smoke_test.py "광주 팝업" --limit 3
   ```
   출력에 PGVECTOR_CONNECTION / VECTOR_COLLECTION 이 표시되고 1개 이상 결과가 나오면 연결 성공입니다.

## 3. systemd + Uvicorn 서비스 구성

`/etc/systemd/system/itdaing-chatbot.service` 예시:

```
[Unit]
Description=Itdaing Chatbot API
After=network.target

[Service]
WorkingDirectory=/home/ubuntu/chaatbot
EnvironmentFile=/home/ubuntu/chaatbot/chatbot.env
ExecStart=/home/ubuntu/chaatbot/.venv/bin/uvicorn chatbot.api.fastapi_app:app --host 0.0.0.0 --port 9000 --workers 2
Restart=on-failure
User=ubuntu
Group=ubuntu

[Install]
WantedBy=multi-user.target
```

배포 순서:

```bash
python3 -m venv /home/ubuntu/chaatbot/.venv
source /home/ubuntu/chaatbot/.venv/bin/activate
pip install -r requirements.txt
sudo systemctl daemon-reload
sudo systemctl enable --now itdaing-chatbot
sudo journalctl -u itdaing-chatbot -f
```

## 4. Nginx 및 네트워크 정책

- `/api/` 라우팅은 그대로 Spring Boot(127.0.0.1:8080)으로 유지.
- `/ai/` → `10.0.144.23:9000` 경로는 개발/QA 중에만 오픈하고, 운영 전환 시에는 제거하거나 소스 IP 제한.
- 보안 그룹 권장 설정
  - Spring Private EC2 SG → chatbot-ec2:9000 **허용**
  - 외부 인터넷 → chatbot-ec2:9000 **차단**
- CloudWatch 지표
  - CPU/메모리/네트워크(CW Agent) 알람 구성
  - `/health`를 주기적으로 호출하는 ALB Target Group 헬스체크 설정

## 5. Spring ↔ Python 계약 검증 절차

1. Spring에서 `/api/chat` 호출 시 request/response 로그를 JSON 형태로 남김.
2. FastAPI `/chat` 로그에서도 `user_id`, `session_id`, `bot_type`, `trace_id`를 INFO 레벨로 출력.
3. 계약 변경 시 `docs/chatbot_api_ops.md`의 JSON 스니펫을 수정하고 양쪽 코드에서 동시 업데이트.
4. curl 시나리오 (Spring 없이 직접 테스트):
   ```bash
   curl -s http://10.0.144.23:9000/chat \
     -H 'Content-Type: application/json' \
     -d '{"bot_type":"SELLER","user_id":"qa","session_id":"sess-qa","message":"부스 배치 알려줘"}' | jq .
   ```

5. LangSmith 태깅: FastAPI는 `tags=["itdaing-chatbot", bot_type, "client:<name>"]`와 `metadata={user_id, session_id, bot_type, history...}`를 LangGraph config에 주입하며, 실패 시 `meta.extra.langgraph_error` 필드에 오류 메시지를 기록합니다.

## 6. QA → 롤아웃 플랜

1. **내부 QA**: QA 계정 2~3개로 `/api/chat` 사용, LangSmith 대시보드에서 trace 확인.
2. **부분 롤아웃**: 특정 사용자 그룹에만 플래그 노출, 에러율/응답시간 모니터링.
3. **전체 롤아웃**: 문제 없을 경우 전체 사용자에게 기능 개방.
4. **회귀 테스트**: `python scripts/run_test_prompts.py --input data/test_prompts.json --output results/test_prompts_results_latest.json` 실행 후 결과를 저장.
5. **장애 대응**: FastAPI 장애 시 Nginx에서 `/chat` 라우팅을 임시 503으로 돌리고, Spring에서 Graceful fallback 응답(“챗봇 점검 중”)을 반환.

---

이 문서는 `CHATBOT_DB.md`와 함께 챗봇 운영의 기준 문서로 유지합니다. 변경 사항이 생기면 두 문서 모두 업데이트하세요.
