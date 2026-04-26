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

## M4 — Alerts + Telegram

새 의존성: `respx>=0.21` (dev 그룹, Telegram HTTP mocking용). 런타임 의존성은 기존 `httpx`/`cryptography`/`sqlalchemy`로 충분.

### 데이터

- `alerts` 테이블: 분석 완료/실패, 시그널 변경, 신뢰도 변동, 스케줄 실패 이벤트가 영구 기록된다. 미읽음 상태(`read=False`)로 시작하며 `/alerts`에서 필터·읽음 처리.
- `settings` 테이블: 한 행 = 한 키. `telegram_bot_token`만 `cryptography.Fernet`으로 암호화되어 `encrypted_value`(BLOB)에 저장된다. 다른 키는 `value`(JSON 텍스트). 키 화이트리스트는 `tradingagents_web/services/settings_store.py:NOTIFICATION_DEFAULTS`.

### Telegram 봇 설정 (선택)

1. BotFather(`@BotFather`)로 봇 생성 → API 토큰 획득.
2. 봇과 1:1 대화 시작 → `https://api.telegram.org/bot<TOKEN>/getUpdates` 응답에서 `chat_id` 확인.
3. 웹 UI `/settings/notifications`에서 토큰 + chat ID 입력 → "Send test message"로 검증.
   - 토큰은 항상 `password` 입력으로 마스킹되며 응답에는 `telegram_bot_token_set: bool` 플래그만 노출된다.
   - 빈 토큰을 저장하면 행이 삭제되어 알림이 in-app만으로 폴백된다.

### 트리거 동작 (기본값)

| 트리거 | 기본 ON/OFF | 설명 |
|---|---|---|
| `signal_change` | ON | 같은 ticker의 직전 `completed` 분석과 결정이 다르면(BUY⇄HOLD⇄SELL) 발화 |
| `confidence_change` | ON (`threshold=0.10`) | `\|Δconfidence\| >= threshold`일 때 발화. threshold 비우면 비활성 |
| `run_failed` | ON | 분석 status가 failed로 끝나면 항상 발화 (in-app + Telegram) |
| `schedule_failed` | ON | APScheduler 트리거가 예외로 끝나면 발화 |
| `run_completed` | OFF | 모든 완료 알림. 시끄러우니 기본 OFF |

설정은 `/settings/notifications`에서 토글하거나 `PUT /api/settings/notifications`로 부분 업데이트한다.

### 사용 흐름

1. (옵션) `/settings/notifications`에서 Telegram 토큰·chat ID 저장 후 "Send test message"로 검증.
2. `/run`으로 분석 실행, 또는 `/schedules`/holding monitor로 자동 분석 누적.
3. 같은 ticker의 결정이 바뀌거나 신뢰도가 임계값 이상 움직이면 `/alerts`에 행이 쌓이고 데스크톱 헤더 벨 아이콘에 미읽음 카운트가 갱신된다(폴링 30s).
4. `/alerts`에서 type/unread 필터링, 개별 "Mark read" 또는 "Mark all read".
5. Telegram이 설정되어 있으면 같은 이벤트가 동시에 chat으로 push된다.

### 주의

- 알림 디스패처(`tradingagents_web/services/notifier.py`)는 모든 내부 예외를 삼키도록 설계되어 있다 — 알림 실패가 분석 파이프라인을 절대 중단시키지 않는다.
- Telegram 클라이언트(`tradingagents_web/services/telegram.py`)는 HTTP 에러뿐만 아니라 비-JSON 응답(`json.JSONDecodeError`)도 잡아서 False/`{ok: False}`로 변환한다.
- `ENCRYPTION_KEY` 환경변수가 비어 있으면 `settings_store`가 부팅 시 토큰 암복호화에서 RuntimeError를 던진다 — `.env.example`의 키를 그대로 두지 말 것.
- 미읽음 카운트 폴링 주기를 줄이고 싶으면 `web/hooks/use-unread-count.ts`의 `refetchInterval`을 조정한다.
