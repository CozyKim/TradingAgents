# TradingAgents Web — Local Development

## One-time setup

```bash
# 1. Install Python deps (uv recommended)
uv sync

# 2. Install frontend deps
(cd web && npm install)

# 3. Generate secrets and copy env
cp .env.example .env
uv run python -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())" >> .env
uv run python -c "import secrets; print('WEB_SESSION_SECRET=' + secrets.token_urlsafe(32))" >> .env
# (Edit .env to remove the placeholder ENCRYPTION_KEY/WEB_SESSION_SECRET lines.)

# 4. Run migrations + create initial password
uv run alembic upgrade head
uv run tradingagents-web set-password
```

## Run (two terminals)

```bash
# Terminal 1: backend
uv run uvicorn tradingagents_web.main:app --reload --port 8000

# Terminal 2: frontend
cd web && npm run dev
```

Open http://localhost:3000 — you'll be redirected to /login.

## Run via docker-compose

```bash
docker compose up --build api web
```

The api service runs migrations automatically on start. To set the initial password
inside the container:

```bash
docker compose exec api tradingagents-web set-password
```

## Tests

```bash
uv run pytest tests/web/ -v       # backend
cd web && npm run typecheck       # frontend type check
cd web && npm run build           # frontend build
```

## M2 — Run/History

### Quick demo (no LLM cost, fake runner)

1. `WEB_FAKE_RUNNER=true uv run uvicorn tradingagents_web.main:app --reload`
2. `cd web && npm run dev`
3. 브라우저 `http://localhost:3000`. 로그인 후:
   - `/run`에서 ticker `AAPL`, 분석가 4종 체크 → "Run"
   - `/run/<id>`로 자동 이동, 가짜 진행과 verdict 확인
   - `/history`에서 방금 분석이 목록에 보이는지 확인 → 클릭 → 상세 보고서

### Real run (LLM 비용 발생)

`WEB_FAKE_RUNNER=false`로 두고(기본) 환경변수에 LLM provider 키 설정. M2는 `tradingagents/default_config.py`의 기본 모델을 사용한다. 모델 변경 UI는 M5에서 추가 예정.

## M3 — Portfolio + Schedules

새 의존성: `apscheduler>=3.10`, `croniter>=2.0`. 기존 `uv sync` 후 사용 가능.

### 새 환경변수

| 이름 | 기본값 | 설명 |
|---|---|---|
| `WEB_SCHEDULE_TZ` | `America/New_York` | APScheduler 타임존 |
| `WEB_SCHEDULER_GRACE_SECONDS` | `60` | misfire grace 시간 |

### 사용 흐름

1. `/portfolio`에서 보유 종목 추가 (ticker / qty / avg cost / notes).
2. monitor 스위치 ON → 평일 16:30 ET 자동 분석 스케줄이 자동 생성됨 (`/schedules`에 `source=holding` 행으로 노출).
3. `/schedules/new`에서 사용자 정의 cron + 다중 티커 등록 가능 (티커가 여러 개면 동일 cron으로 N개 row 생성).
4. `/schedules`의 `Run now` 버튼으로 즉시 분석 트리거 → `/history`에서 결과 확인.
5. `/portfolio/<TICKER>`에서 90일 가격 차트 + 분석 시그널 마커(BUY/SELL/HOLD 점) + 분석 히스토리 타임라인 확인.
6. Dashboard `/`에서 평가액·미실현 P&L·보유 종목 시그널 테이블·진행 중 분석 일람.

### 주의

- 스케줄러는 `MemoryJobStore` 기반이므로 서버 재시작 시 `schedules` 테이블의 `active=True` 항목이 lifespan에서 다시 등록된다.
- `WEB_FAKE_RUNNER=true`로 LLM 호출 없이 전체 흐름을 검증할 수 있다.
- 가격 데이터는 yfinance를 5분 TTL 인메모리 캐시로 호출한다. 오프라인이면 차트가 비어 보일 수 있다.
- 신호 변경 알림(in-app + Telegram)은 M4에서 추가된다 — M3는 분석 자동 실행까지만.
