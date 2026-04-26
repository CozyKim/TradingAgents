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

SSE for run progress is proxied same-origin through a Next.js Route Handler
(`web/app/api/runs/[id]/stream/route.ts`), so only port 3000 needs to be
reachable from the client (LAN, port-forwarded WAN, or reverse proxy). The
backend can stay on `localhost:8000`.

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

## M5 — Polish (PWA, Compare, Account)

신규 의존성 없음. 기존 `httpx`/`sqlalchemy`/`bcrypt` + Next.js 14 그대로.

### PWA 설치

- 매니페스트 `web/public/manifest.json`, 서비스 워커 `web/public/sw.js`, 오프라인 폴백 `web/public/_offline.html`.
- 서비스 워커는 production 빌드에서만 등록된다 (`web/components/shared/service-worker-registrar.tsx`가 `process.env.NODE_ENV === "production"` 가드). dev에서는 캐시 오염을 피한다.
- 캐시 전략:
  - `/api/*` — SW가 손대지 않음(항상 네트워크).
  - `/_next/static/*`, `/icons/*` — cache-first.
  - 같은 출처 HTML 네비게이션 — network-first → 캐시 → `/_offline.html` 폴백.
- 캐시 무효화: `web/public/sw.js` 상단의 `CACHE_NAME`을 다음 배포에서 올린다(예: `ta-v1` → `ta-v2`). activate 핸들러가 이전 버전 캐시를 일괄 삭제한다.
- 아이콘은 placeholder 단색 PNG (192/512). 실제 디자인 자산이 생기면 `web/public/icons/`에 같은 파일명으로 덮어쓴다.

### History 비교 뷰

- `/history` 행마다 체크박스. 최대 2개까지만 선택 가능(세 번째 클릭 시 가장 먼저 선택된 항목이 빠짐).
- "Compare" 버튼은 정확히 2개 선택 시 활성화 → `/history/compare?ids=A,B`로 이동.
- 데스크톱은 `grid-cols-2`로 좌우 분할, 모바일은 단일 컬럼 + 상단 A/B 탭 토글.
- 동일 ID 두 개 또는 ID 개수가 0/1/3+면 안내 메시지를 노출.

### Account / 백업·복원

- `/settings/account` 페이지에서:
  - 비밀번호 변경 (현재 비밀번호 검증 + 다른 세션 일괄 로그아웃 토글).
  - 활성 세션 목록 (마스킹된 토큰, 만료시각, 현재 세션 표시) + "Revoke other sessions".
  - 백업 다운로드: `GET /api/settings/account/backup`이 라이브 SQLite 파일을 `tradingagents-backup-YYYYMMDD-HHMMSS.db`로 첨부 다운로드한다 (`PRAGMA wal_checkpoint(TRUNCATE)` 선행).
  - 복원: 다운받았던 `.db` 파일을 업로드. 백엔드는 `services/db_admin.run_restore`로 (1) SQLite 매직 헤더 + integrity_check + 7개 테이블 검증, (2) 스케줄러 종료, (3) 바인딩 엔진 dispose, (4) 파일 교체, (5) 스케줄러 재기동을 수행. 복원 직후 모든 세션이 무효화되어 사용자가 자동으로 `/login`으로 이동한다.
- 복원은 SQLite 배포 한정 — `database_url`이 sqlite로 시작하지 않으면 backup/restore 둘 다 `409 Conflict`.

### 모바일 More 페이지

- 하단 탭바의 `/more` 링크가 신규 `web/app/(workspace)/more/page.tsx`로 연결된다 — History/Schedules/Notifications/Account 카드 리스트 + Logout 버튼.
- 사이드바 System 섹션도 Notifications + Account 두 항목으로 확장.

### 주의

- 복원 endpoint(`POST /api/settings/account/restore`)는 라이브 DB를 교체하므로 운영에서는 사전 백업을 항상 권장. 실패 시 staging 파일을 자동 정리하지만 디스크가 가득 차면 staging이 남을 수 있으므로 `<data_dir>/restore.staging.db`가 있는지 점검 가능.
- 서비스 워커는 same-origin HTML 캐시를 보관하므로 새 배포 후에도 한 번은 강제 새로고침이 필요할 수 있다(또는 PWA를 재설치). `CACHE_NAME` 버전을 올리면 자동으로 정리된다.
- 백업 파일에는 평문 분석 보고서·암호화된 토큰·세션 토큰이 모두 들어 있다 — 외부 공유는 피하고, 다운로드 즉시 안전한 곳으로 이동시킬 것.
