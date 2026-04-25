# TradingAgents Web — 설계 명세서

- **작성일**: 2026-04-25
- **상태**: 설계 확정 (구현 미착수)
- **대상**: 단일 사용자(개인 서버), 다크 모던 데이터 밀집형 반응형 웹

## 1. 목적과 범위

### 1.1 목적

기존 CLI 기반 `tradingagents` 프레임워크를 단일 사용자용 웹 워크벤치로 옮긴다. 매번 새로 분석을 돌리고 결과를 휘발시키는 CLI의 한계를 넘어, **분석 실행 → 결과 누적 → 비교 → 보유 종목 자동 모니터링 → 시그널 알림**까지 한 화면에서 처리한다.

### 1.2 범위 (In Scope)

- 분석 실행 (즉시 / 백그라운드)
- 분석 히스토리 영구 저장, 검색, 비교
- 보유 종목 입력 및 자동 모니터링
- 스케줄 기반 자동 분석 (cron)
- 시그널 변경·완료·실패 알림 (in-app + Telegram)
- LLM 프로바이더·모델·데이터 벤더 설정
- 단일 사용자 비밀번호 인증
- 모바일/태블릿/데스크톱 반응형 + PWA 설치 지원

### 1.3 범위 외 (Out of Scope)

- **자동 매매 / 주문 실행**: 시그널만 제공, 거래는 사용자가 외부에서 수행
- 다중 사용자, 권한 관리, 팀/공유
- 백테스팅 엔진(별도 프로젝트로 분리 가능)
- 모바일 네이티브 앱 (PWA로 충분)
- 대규모 가격 스트리밍·차트 라이브 시세 (yfinance 분 단위 폴링 정도)

## 2. 사용자 시나리오

다음 5가지 핵심 시나리오를 만족해야 한다.

### S1. 즉시 분석 (Run on demand)

> "AAPL을 지금 분석하고 결과를 보고 싶다."

`/run`에서 티커 입력 → LLM/분석가 옵션 확인 → "Run" → `/run/:runId`에서 라이브 스트림(에이전트별 출력 + 진행 게이지) 관찰 → 완료 시 결정·신뢰도·근거 보고서. 결과는 자동으로 `analyses`에 저장.

### S2. 과거 분석 비교

> "지난주 NVDA 분석과 오늘 분석을 나란히 보고 싶다."

`/history`에서 티커 필터·날짜 정렬 → 두 항목 체크 → "Compare" → `/history/compare?ids=a,b`에서 좌우 분할 보기(결정 변화, 토론 차이, 가격 변화).

### S3. 보유 종목 자동 모니터링

> "내가 가진 8개 종목을 매일 한 번씩 알아서 분석하고 BUY/SELL 변경되면 알려줘."

`/portfolio`에서 종목 추가(수량·평균 매입가) → 종목별 "Auto-monitor" ON → 백엔드가 일일 cron 스케줄 자동 등록 → 매일 장 마감 후 분석 실행 → 시그널이 직전 결과와 다르면 Telegram + in-app 알림.

### S4. 사용자 정의 스케줄

> "매주 월요일 오전 9시에 반도체 종목 묶음을 분석하고 싶다."

`/schedules/new`에서 종목 다중 선택 + cron 표현식 + 분석 프리셋 → 등록. APScheduler가 큐잉.

### S5. 모바일에서 알림 확인

> "Telegram 알림 받았는데 출퇴근 중에 빠르게 결과 보고 싶다."

휴대폰에서 PWA 설치 → 홈 화면 아이콘 탭 → 비밀번호(또는 저장된 세션) → 하단 탭바 Alerts → 항목 탭 → 분석 상세(모바일 단일 컬럼).

## 3. 정보 구조 (라우팅)

7개 톱레벨 섹션. 라우트는 Next.js App Router 기준.

| 섹션 | 라우트 | 화면 요약 |
|---|---|---|
| Dashboard | `/` | 총평가액·P&L 카드, 보유 종목 신호 테이블, 진행 중 분석, 최근 알림 |
| Run | `/run` | 새 분석 폼 (ticker / date / 분석가 / LLM 모델 / debate rounds) |
| Run Live | `/run/:runId` | 실시간 진행 + 에이전트 출력 SSE 스트림 |
| History | `/history` | 분석 목록, 필터(ticker/date/decision/confidence), 즐겨찾기 |
| History Detail | `/history/:runId` | 완료된 분석 상세 보고서 |
| History Compare | `/history/compare?ids=a,b` | 좌우 분할 비교 |
| Portfolio | `/portfolio` | 보유 종목 리스트, 모니터링 토글, P&L |
| Portfolio Detail | `/portfolio/:ticker` | 가격 차트 + 시그널 변화 타임라인 + 분석 히스토리 |
| Schedules | `/schedules` | 등록된 스케줄, 다음 실행, 일시정지 |
| Schedule New | `/schedules/new` | 종목·cron·프리셋 |
| Alerts | `/alerts` | 알림 히스토리, 읽음 표시, 필터 |
| Settings | `/settings/llm` | Provider, deep/quick 모델, API 키 |
| Settings | `/settings/data` | 데이터 벤더 (yfinance / Alpha Vantage) |
| Settings | `/settings/notifications` | Telegram 봇 토큰, 트리거 임계값 |
| Settings | `/settings/account` | 비밀번호, 세션, 데이터 백업 |
| Auth | `/login` | 비밀번호 로그인 |

### 3.1 네비게이션 매핑

- **데스크톱 사이드바 (≥1280px)**: Workspace(Dashboard, Run, History) → Tracking(Portfolio, Schedules, Alerts) → System(Settings)
- **태블릿 (768–1279px)**: 사이드바가 아이콘만으로 접힘. 호버 시 라벨 툴팁. 라이브 패널은 슬라이드오버.
- **모바일 (<768px)**: 하단 탭바 5개 — `Home / Portfolio / +Run(중앙 FAB) / Alerts / More`. "More"에 History·Schedules·Settings 모음. Run을 FAB으로 배치하는 이유는 모바일에서 가장 자주 쓰는 액션이라서.

## 4. 시각 디자인

### 4.1 디자인 토큰

```css
/* Background */
--bg-0: #0a0a0b;   /* 페이지 */
--bg-1: #111114;   /* 카드/패널 */
--bg-2: #18181c;   /* 호버/액티브 */

/* Border */
--border-1: #1f1f24;
--border-2: #25252b;

/* Text */
--text-1: #e8e8ea;  /* 주요 */
--text-2: #a0a0a8;  /* 보조 */
--text-3: #6b6b74;  /* 라벨 */

/* Brand & Signals */
--accent: #4f8cff;     /* 브랜드 블루 */
--pos:    #34d399;     /* BUY / 상승 — 민트 */
--neg:    #f87171;     /* SELL / 하락 — 코랄 */
--warn:   #fbbf24;     /* HOLD / 주의 — 앰버 */

/* Typography */
--font-sans: "Inter", -apple-system, sans-serif;
--font-mono: "JetBrains Mono", "SF Mono", monospace;

/* Radius */
--r-sm: 4px;
--r-md: 6px;
--r-lg: 8px;
--r-xl: 12px;
```

### 4.2 컴포넌트 원칙

- **카드 보더**: 모든 패널은 1px `--border-1` + radius 6–8px.
- **시그널 뱃지**: `bg = signal_color * 0.15 alpha`, `text = signal_color`. 어디서나 동일.
- **숫자/티커**: 반드시 모노스페이스. 정렬 깨짐 방지.
- **본문/라벨**: Inter. 라벨은 9–10px uppercase + letter-spacing 0.5–1px.
- **그라디언트 액센트**: 결정 카드(verdict)와 모바일 hero 카드에만 절제하여 사용.
- **애니메이션**: 라이브 인디케이터 펄스(1.4s), 카드 hover translateY(-2px) 0.15s. 그 외 최소화.

### 4.3 화면별 레이아웃 핵심

**Dashboard (데스크톱)**
- 3분할: `사이드바(180px) | 메인(가변) | 라이브패널(320px)`.
- 메인 = 메트릭 3카드(평가액/P&L/포지션) + Holdings 테이블.
- 라이브패널 = 진행 중 분석이 있을 때만 표시. 없으면 자리만 비움(혹은 hidden).

**Run Live**
- 좌측: 진행 게이지 + 단계별 체크리스트.
- 우측: 에이전트별 메시지 카드(border-left 색상 = 역할). SSE로 한 줄씩 추가.
- 하단: Verdict 카드(완료 시 그라디언트 액센트, 진행 중일 때는 "Preliminary").

**History Compare**
- 좌우 동일 구조. 헤더에 두 분석의 메타(티커/날짜/모델) 비교 뱃지.
- 스크롤 동기화 옵션.

**Portfolio Detail**
- 상단: 보유 정보 카드.
- 가운데: Recharts 가격 라인 + 시그널 마커(BUY/SELL/HOLD 점).
- 하단: 분석 히스토리 타임라인 (시간 역순 카드 리스트).

### 4.4 반응형 적응 패턴

- 테이블 → 모바일에서는 카드 리스트 (티커/뱃지/가격/수익률을 한 카드에).
- 우측 라이브 패널 → 모바일에서는 별도 라우트(`/run/:id`) 또는 바텀시트.
- 그라디언트 hero 카드는 모바일 Dashboard 상단에만 (총 평가액 강조).

## 5. 시스템 아키텍처

### 5.1 전체 구성

```
┌────────────────────────────────────────────────┐
│  Next.js (App Router, TypeScript)              │
│  - Tailwind + shadcn/ui                         │
│  - Recharts, TanStack Query                     │
│  - next-pwa (manifest + SW)                     │
└─────────────────┬──────────────────────────────┘
                  │  fetch / SSE / cookie session
┌─────────────────▼──────────────────────────────┐
│  FastAPI (Python 3.10+, uv)                    │
│  ├─ /api/auth     (login, logout, session)     │
│  ├─ /api/runs     (CRUD + SSE stream)          │
│  ├─ /api/holdings (CRUD)                       │
│  ├─ /api/schedules (CRUD)                      │
│  ├─ /api/alerts   (list, mark-read)            │
│  └─ /api/settings (LLM/data/notif/account)     │
│                                                │
│  Workers                                       │
│  ├─ APScheduler (cron jobs)                    │
│  └─ FastAPI BackgroundTasks (즉시 분석)        │
│                                                │
│  Core                                          │
│  └─ tradingagents.graph.TradingAgentsGraph     │
│                                                │
│  Storage                                       │
│  └─ SQLite (~/.tradingagents/data.db)          │
└────────────────────────────────────────────────┘
                  │
                  ▼
        Telegram Bot API (알림 push)
```

### 5.2 백엔드 모듈 경계

`tradingagents_web/` 신규 패키지 추가 (기존 `tradingagents/`는 그대로 임포트해서 사용).

```
tradingagents_web/
├── api/
│   ├── auth.py
│   ├── runs.py        # POST /runs, GET /runs/{id}/stream (SSE)
│   ├── holdings.py
│   ├── schedules.py
│   ├── alerts.py
│   └── settings.py
├── services/
│   ├── runner.py      # TradingAgentsGraph 호출 + SSE 브로드캐스트
│   ├── scheduler.py   # APScheduler 래퍼
│   ├── notifier.py    # Telegram + in-app 알림 디스패치
│   └── crypto.py      # API 키 암호화 (cryptography.Fernet)
├── models/            # SQLAlchemy ORM
│   ├── user.py
│   ├── analysis.py
│   ├── holding.py
│   ├── schedule.py
│   ├── alert.py
│   └── setting.py
├── db.py              # 세션 팩토리, 마이그레이션 (alembic)
├── config.py
├── auth.py            # 비밀번호 해시, 세션 쿠키
└── main.py            # FastAPI 앱 부트
```

각 모듈의 책임은 단일하다. `runner`는 그래프 실행만, `notifier`는 알림만, `scheduler`는 cron만 담당. 데이터 액세스는 모두 `models/` 경유.

### 5.3 프런트엔드 모듈 경계

```
web/                               # Next.js 앱 루트
├── app/
│   ├── (auth)/login/page.tsx
│   ├── (workspace)/
│   │   ├── layout.tsx             # 사이드바 + 탭바
│   │   ├── page.tsx               # Dashboard
│   │   ├── run/page.tsx
│   │   ├── run/[id]/page.tsx
│   │   ├── history/...
│   │   ├── portfolio/...
│   │   ├── schedules/...
│   │   ├── alerts/...
│   │   └── settings/...
│   └── api/health/route.ts
├── components/
│   ├── ui/                        # shadcn/ui 베이스
│   ├── nav/sidebar.tsx
│   ├── nav/tab-bar.tsx
│   ├── analysis/agent-card.tsx
│   ├── analysis/verdict-card.tsx
│   ├── portfolio/holdings-table.tsx
│   └── shared/signal-badge.tsx
├── lib/
│   ├── api.ts                     # fetch 래퍼 + 쿠키 인증
│   ├── sse.ts                     # EventSource 헬퍼
│   ├── tokens.ts                  # 디자인 토큰 export
│   └── format.ts                  # 통화·퍼센트 포매터
├── hooks/
│   ├── use-runs.ts                # TanStack Query
│   └── use-sse-run.ts             # 라이브 스트림 구독
└── public/
    ├── manifest.json
    └── icons/...
```

### 5.4 라이브 스트리밍

LangGraph가 노드별 결과를 produce할 때마다 백엔드가 SSE 이벤트를 emit한다.

```
GET /api/runs/{run_id}/stream     (text/event-stream)

event: agent_message
data: {"role":"bull","text":"...","ts":...}

event: progress
data: {"step":3,"total":5}

event: done
data: {"decision":"BUY","confidence":0.78}
```

프런트는 `EventSource`로 구독해 라이브 패널을 점진적으로 채운다. 연결 끊김 시 자동 재연결.

## 6. 데이터 모델

SQLAlchemy + alembic 마이그레이션. 모든 시간은 UTC ISO 8601.

### 6.1 테이블

```python
# users — 단일 행 (id=1)
id: int PK
password_hash: str (bcrypt)
created_at: datetime

# analyses — 모든 분석 결과 영구 저장
id: int PK
run_id: str (uuid) UNIQUE
ticker: str (인덱스)
analysis_date: date         # 분석 대상 날짜
status: enum(running, completed, failed, cancelled)
decision: enum(BUY, SELL, HOLD) NULL until done
confidence: float NULL
llm_provider: str
llm_deep_model: str
llm_quick_model: str
debate_rounds: int
analysts: JSON              # ["fundamentals","sentiment","news","technical"]
final_state: JSON NULL      # LangGraph 최종 상태 (보고서, 차트 데이터 포함)
error: str NULL
cost_usd: float NULL
created_at: datetime (인덱스)
completed_at: datetime NULL
schedule_id: int FK NULL    # 자동 분석인 경우 출처

# holdings — 보유 종목
id: int PK
ticker: str UNIQUE
qty: float
avg_cost: float
monitor_enabled: bool       # True면 schedule에 자동 등록
notes: str NULL
created_at: datetime
updated_at: datetime

# schedules — 자동 분석 cron
id: int PK
name: str
ticker: str (인덱스)
cron_expr: str              # APScheduler cron 표현식
preset: JSON                # llm/analysts/debate_rounds
active: bool
last_run: datetime NULL
next_run: datetime NULL
created_at: datetime

# alerts — 알림 히스토리
id: int PK
type: enum(signal_change, run_completed, run_failed, schedule_failed)
ticker: str NULL
analysis_id: int FK NULL
payload: JSON               # {"prev":"HOLD","curr":"BUY","confidence":0.78,...}
read: bool DEFAULT False
created_at: datetime (인덱스)

# settings — 키-값 설정 (민감값 암호화)
key: str PK
value: str                  # 평문
encrypted_value: bytes NULL # cryptography.Fernet
updated_at: datetime
```

### 6.2 인덱스

- `analyses(ticker, created_at DESC)`, `analyses(status)`, `analyses(schedule_id)`
- `alerts(read, created_at DESC)`
- `schedules(active, next_run)`

### 6.3 데이터 마이그레이션 / 백업

- alembic으로 스키마 버전 관리.
- `/settings/account`에서 `data.db` 파일 다운로드 = 전체 백업 (단일 파일이므로 단순).

## 7. 인증 및 보안

- **로그인**: 단일 사용자, bcrypt 해시 비밀번호. 첫 실행 시 CLI 명령(`tradingagents-web set-password`)으로 설정 — 환경변수에 평문 비밀번호를 두지 않는다.
- **세션**: HttpOnly + Secure + SameSite=Strict 쿠키, 30일 슬라이딩 만료. 서버 측 세션 ID + DB 검증.
- **CSRF**: SameSite=Strict가 기본 방어. 변경 API에 추가로 `X-Requested-With` 헤더 검사.
- **API 키 보호**: LLM provider 키, Telegram 토큰은 `cryptography.Fernet`으로 암호화해 `settings.encrypted_value`에 저장. 마스터 키는 환경변수 `ENCRYPTION_KEY` (서버 부팅 시 주입).
- **HTTPS**: 운영 환경은 caddy/nginx 리버스 프록시로 TLS 종단.
- **로그 위생**: API 키, 비밀번호, 세션 토큰 절대 로깅 금지. Pydantic 모델에 `SecretStr` 사용.

## 8. 알림

### 8.1 트리거

1. **시그널 변경**: 같은 종목의 직전 완료 분석 결정과 비교해 BUY⇄SELL⇄HOLD 변경 시 발화.
2. **신뢰도 큰 변화**: 임계값(기본 ±10%) 이상 변하면 발화 (선택).
3. **분석 완료**: 사용자 토글로 켤 수 있음 (기본 OFF, 시끄러우니까).
4. **분석 실패 / 스케줄 실패**: 항상 발화.

### 8.2 채널

- **In-app**: `/alerts`에 항상 기록. Dashboard 우상단 벨 아이콘에 미읽음 카운트.
- **Telegram**: `/settings/notifications`에서 봇 토큰·chat_id 설정 시 활성화. `notifier.send_telegram()`으로 push.

## 9. 배포

- **Docker compose** 한 방 배포. 두 컨테이너:
  - `web`: Next.js (production build, `node` 이미지) — 정적 + SSR 처리
  - `api`: FastAPI (uvicorn + gunicorn worker) + SQLite 볼륨 (`~/.tradingagents/`)
- 리버스 프록시(caddy/nginx)는 호스트에 별도 또는 compose에 추가.
- 환경변수: `INITIAL_PASSWORD`, `ENCRYPTION_KEY`, LLM API 키들, `TELEGRAM_BOT_TOKEN`(옵션).

## 10. 테스트 전략

- **백엔드**: `pytest` — API 라우트(인증/분석/홀딩/스케줄), 서비스 모듈(runner, scheduler, notifier 모킹), 모델/마이그레이션. 목표 커버리지 ≥ 80%.
- **프런트**: 컴포넌트 단위 테스트는 핵심 컴포넌트(SignalBadge, HoldingsTable, AgentCard)만. E2E는 Playwright로 핵심 시나리오(S1, S3, S5) 1개씩.
- **통합**: docker-compose up 후 health check 스크립트 — 로그인 → 분석 1건 실행 → 히스토리 조회 성공.

## 11. 단계별 구현 (마일스톤)

이 섹션은 큰 흐름만. 세부 단계는 다음 단계의 implementation plan에서 다룬다.

1. **M1 — 뼈대**: FastAPI 앱 + SQLite + alembic 초기 스키마 + Next.js 부트 + 로그인.
2. **M2 — Run/History**: 분석 실행(SSE 스트림 포함), 히스토리 목록·상세.
3. **M3 — Portfolio + Schedules**: 보유 종목 + APScheduler 자동 분석.
4. **M4 — Alerts + Telegram**: 시그널 변경 감지 + 알림 채널.
5. **M5 — 폴리싱**: PWA(매니페스트, SW), 모바일 폴리싱, 비교 뷰, 백업/복원.

## 12. 위험 요소와 대응

- **LangGraph 실행 시간 변동성** (큰 토론 라운드는 수 분): SSE로 진행 상황 노출, 클라이언트 타임아웃 비활성, 백그라운드 실행 + 알림으로 대체.
- **API 비용 폭주**: `analyses.cost_usd` 누적 표시, Settings에 일일 한도 + 한도 초과 시 신규 실행 차단.
- **SQLite 동시성 한계**: 단일 사용자라 충분. 단, APScheduler 워커가 여러 분석 병렬 실행 시 WAL 모드 필수(`PRAGMA journal_mode=WAL`).
- **API 키 누출**: 절대 로그/응답 본문에 노출 금지. Settings 응답은 키를 `***`로 마스킹.
- **모바일 PWA 캐시 stale**: SW 전략을 `network-first`로(분석 데이터), 정적 자산만 `cache-first`.

## 13. 디렉토리 변경 요약

신규:

```
tradingagents_web/        # 백엔드 신규 패키지
web/                      # Next.js 프런트엔드
docs/superpowers/specs/   # 본 명세서 위치
```

기존 변경:

- `pyproject.toml`: `fastapi`, `sqlalchemy`, `alembic`, `apscheduler`, `cryptography`, `sse-starlette`, `python-telegram-bot` 추가.
- `Dockerfile`, `docker-compose.yml`: 멀티 서비스 구성으로 확장.
- `tradingagents/`: 변경 최소화. 그래프 실행 시 콜백 인터페이스 노출이 필요하면 작은 훅 추가(노드 출력을 외부로 전달).

## 14. 오픈 이슈

다음은 implementation plan에서 결정/구체화한다.

- LangGraph 노드 출력을 SSE로 push하는 정확한 인터셉트 지점(현재 `debug=True`로 stdout 출력 → 파싱 vs callback 추가).
- 세션 저장소: SQLite 추가 테이블 vs 메모리 dict + `signed cookie`.
- 사용량/비용 추적의 토큰 카운트 출처(LangChain 콜백 vs 자체 측정).
- alembic 마이그레이션 워크플로우(개발/배포 분리).
