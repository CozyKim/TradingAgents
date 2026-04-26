# TradingAgents Web — M3 Portfolio + Schedules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 사용자가 보유 종목(`holdings`)을 등록하고, 종목별 자동 모니터링을 켜거나 사용자 정의 cron 스케줄을 만들면, APScheduler가 정해진 시각에 분석을 자동 실행해 `analyses` 테이블에 누적하도록 한다. 또한 Dashboard와 `/portfolio/:ticker` 상세 화면에서 보유 정보·가격 차트·시그널 타임라인을 본다.

**Architecture:** SQLite에 `holdings`, `schedules` 테이블을 추가하고, `analyses`에 `schedule_id` FK를 보강한다. APScheduler `AsyncIOScheduler`(MemoryJobStore)를 FastAPI `lifespan`에서 부팅 시 기동·종료한다. `schedules` 테이블이 single source of truth이며 부팅 시 `active=True` 행을 모두 APScheduler에 등록한다. 스케줄 트리거 시 기존 M2 runner 파이프라인을 재사용해 새 `analyses` 행 생성·SSE 이벤트 발행을 그대로 따라간다. `holdings.monitor_enabled` 토글은 종목별 일일 스케줄(`schedules`) 행을 자동으로 생성/삭제하는 얇은 어댑터를 거친다. 가격 데이터는 `yfinance`로 가져와 5분 TTL in-memory 캐시. 프런트는 TanStack Query로 데이터를 가져오고 Recharts로 가격·시그널 라인을 그린다.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, alembic, APScheduler 3.x (`AsyncIOScheduler`, `CronTrigger`), `croniter`(검증), `yfinance`(이미 의존성에 존재), pytest. Next.js 14 App Router, TypeScript, TanStack Query, Recharts 2.x.

**Spec:** [docs/superpowers/specs/2026-04-25-tradingagents-web-design.md](../specs/2026-04-25-tradingagents-web-design.md) — §2 S3·S4, §3, §5(holdings/schedules 라우트), §6(holdings/schedules 스키마), §11(M3)

**Out of scope (다른 플랜에서):**
- Telegram 알림 / Alerts (M4)
- 시그널 변경 감지 로직 자체는 M3 범위가 아니다. M3는 "분석 자동 실행"까지만. Alerts dispatch는 M4.
- 비교 뷰 `/history/compare` (M5)
- Settings UI (`/settings/llm`, `/settings/data`, `/settings/notifications`) — M3는 기본 config 사용
- PWA 매니페스트 / SW (M5)

**의존 결정 (open issues §14에 영향 받는 부분):**

1. **APScheduler jobstore** → `MemoryJobStore`. `schedules` 테이블이 영속 source of truth이므로 jobstore 영속화는 불필요. 부팅 시 `_load_active_schedules()`가 active 행을 등록한다.
2. **Schedule 다중 티커** → 한 행 = 한 티커. 사용자가 폼에서 여러 티커 선택 시 같은 cron 표현식으로 N개 행을 생성한다. 백엔드 단순화 + 개별 토글/삭제가 자연스럽다.
3. **Auto-monitor 기본 cron** → `30 16 * * 1-5` (평일 16:30 ET 가정, 시스템 TZ는 환경변수 `WEB_SCHEDULE_TZ`로 주입; 기본 `America/New_York`).
4. **분석 트리거 흐름** → 스케줄러는 `services.auto_runner.trigger_run()`을 호출. 이 함수는 M2의 `_execute_and_persist`와 동일한 로직(분석 row 생성 + 백그라운드 task 등록)을 공유하므로 `runs.py`에서 `start_analysis_run()` 헬퍼를 추출해 재사용한다.
5. **가격 데이터 캐시** → `services/prices.py`에 `functools.lru_cache` + 만료 timestamp 튜플 패턴(또는 `cachetools.TTLCache`). yfinance 호출은 `asyncio.to_thread`로 감싼다.
6. **Recharts** → `recharts@2` 추가. M2까지는 차트 없음.

---

## File Structure

신규 백엔드:

```
tradingagents_web/
├── models/
│   ├── holding.py             # Holding ORM
│   └── schedule.py            # Schedule ORM
├── schemas/
│   ├── holding.py
│   ├── schedule.py
│   └── price.py
├── services/
│   ├── prices.py              # yfinance + 5분 TTL 캐시
│   ├── scheduler.py           # APScheduler 래퍼 + 부팅 시 active 등록
│   ├── auto_runner.py         # cron 트리거 → 분석 생성
│   └── holdings_sync.py       # holdings.monitor_enabled ↔ schedules 동기화
└── api/
    ├── holdings.py            # CRUD + monitor 토글
    ├── schedules.py           # CRUD + pause/resume + run-now
    └── prices.py              # GET /api/prices/{ticker}/history

migrations/versions/
└── 0003_holdings_schedules.py

tests/web/
├── test_models_holding.py
├── test_models_schedule.py
├── test_prices_service.py
├── test_scheduler_service.py
├── test_auto_runner.py
├── test_holdings_sync.py
├── test_holdings_api.py
├── test_schedules_api.py
└── test_prices_api.py
```

신규 프런트엔드:

```
web/
├── app/
│   └── (workspace)/
│       ├── page.tsx                          # Dashboard (M1 placeholder를 교체)
│       ├── portfolio/
│       │   ├── page.tsx                      # 보유 목록 + 추가
│       │   └── [ticker]/
│       │       └── page.tsx                  # 상세: 가격 차트 + 시그널 + 히스토리
│       └── schedules/
│           ├── page.tsx                      # 스케줄 목록
│           └── new/
│               └── page.tsx                  # 스케줄 생성
├── components/
│   ├── portfolio/
│   │   ├── holding-form.tsx
│   │   ├── holdings-table.tsx
│   │   ├── monitor-toggle.tsx
│   │   ├── pnl-cell.tsx
│   │   └── price-chart.tsx                   # Recharts wrapper
│   ├── schedules/
│   │   ├── schedule-form.tsx
│   │   ├── schedules-table.tsx
│   │   └── cron-helper.tsx                   # cron 표현식 라벨 + presets
│   └── dashboard/
│       ├── metric-card.tsx
│       └── portfolio-signals.tsx
├── hooks/
│   ├── use-holdings.ts
│   ├── use-schedules.ts
│   └── use-price-history.ts
└── lib/
    ├── holdings.ts                           # 타입 + fetch 래퍼
    ├── schedules.ts
    └── prices.ts
```

기존 변경:

- `pyproject.toml`: `apscheduler>=3.10`, `croniter>=2.0` 추가 (yfinance는 기존)
- `tradingagents_web/main.py`: `holdings`/`schedules`/`prices` 라우터 등록 + `lifespan`에서 scheduler 기동/종료
- `tradingagents_web/config.py`: `schedule_tz: str`, `scheduler_grace_seconds: int` 추가
- `tradingagents_web/api/runs.py`: `start_analysis_run()` 헬퍼 추출 (auto_runner와 공유)
- `tradingagents_web/models/analysis.py`: `schedule_id` 컬럼 추가
- `tradingagents_web/models/__init__.py`: `Holding`, `Schedule` export
- `tradingagents_web/schemas/analysis.py`: `AnalysisListItem`/`AnalysisDetail`에 `schedule_id` 노출
- `web/components/nav/sidebar.tsx`: Portfolio·Schedules 활성 처리 (이미 있을 수도, 확인 후 보완)
- `web/package.json`: `recharts@^2.13`, `@radix-ui/react-switch`, `@radix-ui/react-dialog`, `date-fns`(optional, 차트 포매팅) 추가
- `DEV.md`: M3 사용 절차 단락 추가

---

## Task 1: Holding/Schedule 모델 + Analysis.schedule_id FK + alembic 0003

**Files:**
- Create: `tradingagents_web/models/holding.py`
- Create: `tradingagents_web/models/schedule.py`
- Modify: `tradingagents_web/models/analysis.py`
- Modify: `tradingagents_web/models/__init__.py`
- Create: `migrations/versions/0003_holdings_schedules.py`
- Create: `tests/web/test_models_holding.py`
- Create: `tests/web/test_models_schedule.py`

- [ ] **Step 1: 실패하는 모델 테스트 작성**

`tests/web/test_models_holding.py`:

```python
"""Tests for Holding ORM model."""
from datetime import datetime, timezone

from tradingagents_web.models import Holding


def test_holding_minimal_fields(app_with_test_db):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        h = Holding(ticker="AAPL", qty=10.0, avg_cost=150.0)
        db.add(h)
        db.commit()
        db.refresh(h)
        assert h.id > 0
        assert h.monitor_enabled is False
        assert h.notes is None
        assert h.created_at is not None
        assert h.updated_at is not None
    finally:
        db.close()


def test_holding_unique_ticker(app_with_test_db):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        db.add(Holding(ticker="NVDA", qty=1, avg_cost=900.0))
        db.commit()
        db.add(Holding(ticker="NVDA", qty=2, avg_cost=950.0))
        import sqlalchemy.exc
        try:
            db.commit()
            raise AssertionError("expected unique violation")
        except sqlalchemy.exc.IntegrityError:
            db.rollback()
    finally:
        db.close()
```

`tests/web/test_models_schedule.py`:

```python
"""Tests for Schedule ORM model + Analysis.schedule_id FK."""
from datetime import date, datetime, timezone

from tradingagents_web.models import Analysis, Schedule


def test_schedule_minimal_fields(app_with_test_db):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        s = Schedule(
            name="AAPL daily",
            ticker="AAPL",
            cron_expr="30 16 * * 1-5",
            preset={"analysts": ["market"], "debate_rounds": 1},
            active=True,
        )
        db.add(s)
        db.commit()
        db.refresh(s)
        assert s.id > 0
        assert s.last_run is None
        assert s.next_run is None
        assert s.created_at is not None
    finally:
        db.close()


def test_analysis_schedule_id_fk(app_with_test_db):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        s = Schedule(name="x", ticker="X", cron_expr="0 9 * * *", preset={}, active=True)
        db.add(s)
        db.commit()
        a = Analysis(
            run_id="00000000-0000-0000-0000-000000000099",
            ticker="X",
            analysis_date=date(2026, 4, 25),
            status="running",
            llm_provider="openai",
            llm_deep_model="gpt-5.5",
            llm_quick_model="gpt-5.4-mini",
            debate_rounds=1,
            analysts=["market"],
            schedule_id=s.id,
        )
        db.add(a)
        db.commit()
        db.refresh(a)
        assert a.schedule_id == s.id
    finally:
        db.close()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/web/test_models_holding.py tests/web/test_models_schedule.py -v`
Expected: ImportError (`Holding`/`Schedule` not exported) 또는 AttributeError(`schedule_id` 없음).

- [ ] **Step 3: Holding 모델 작성**

`tradingagents_web/models/holding.py`:

```python
"""Holding ORM: a single position the user is tracking."""
from sqlalchemy import Boolean, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from tradingagents_web.models.base import Base, TimestampMixin


class Holding(Base, TimestampMixin):
    """A single ticker position with optional auto-monitoring."""

    __tablename__ = "holdings"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    avg_cost: Mapped[float] = mapped_column(Float, nullable=False)
    monitor_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 4: Schedule 모델 작성**

`tradingagents_web/models/schedule.py`:

```python
"""Schedule ORM: a recurring auto-analysis cron entry."""
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from tradingagents_web.models.base import Base, utcnow


class Schedule(Base):
    """An APScheduler-backed cron entry that triggers an analysis run."""

    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    ticker: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    cron_expr: Mapped[str] = mapped_column(String(64), nullable=False)
    preset: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    last_run: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(String(16), default="user", nullable=False)
    # source: "user" | "holding" — auto-managed schedules created by holdings_sync
    holding_id: Mapped[int | None] = mapped_column(nullable=True)  # informational link

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
```

- [ ] **Step 5: Analysis.schedule_id 컬럼 추가**

`tradingagents_web/models/analysis.py` — 마지막 컬럼 뒤에 한 줄 추가:

```python
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    schedule_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
```

(상단 import는 `Integer`가 이미 있어 변경 불필요.)

- [ ] **Step 6: `__init__.py` export 갱신**

`tradingagents_web/models/__init__.py`:

```python
"""ORM model exports."""
from tradingagents_web.models.analysis import Analysis
from tradingagents_web.models.base import Base, TimestampMixin
from tradingagents_web.models.holding import Holding
from tradingagents_web.models.schedule import Schedule
from tradingagents_web.models.session import Session
from tradingagents_web.models.user import User

__all__ = ["Analysis", "Base", "Holding", "Schedule", "Session", "TimestampMixin", "User"]
```

- [ ] **Step 7: alembic 마이그레이션 작성**

`migrations/versions/0003_holdings_schedules.py`:

```python
"""holdings + schedules tables, analyses.schedule_id

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-25 00:00:02.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "holdings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("qty", sa.Float(), nullable=False),
        sa.Column("avg_cost", sa.Float(), nullable=False),
        sa.Column("monitor_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint("uq_holdings_ticker", "holdings", ["ticker"])
    op.create_index("ix_holdings_ticker", "holdings", ["ticker"])

    op.create_table(
        "schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("cron_expr", sa.String(length=64), nullable=False),
        sa.Column("preset", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("last_run", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False, server_default=sa.text("'user'")),
        sa.Column("holding_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_schedules_ticker", "schedules", ["ticker"])
    op.create_index("ix_schedules_active", "schedules", ["active"])

    with op.batch_alter_table("analyses") as batch:
        batch.add_column(sa.Column("schedule_id", sa.Integer(), nullable=True))
        batch.create_index("ix_analyses_schedule_id", ["schedule_id"])


def downgrade() -> None:
    with op.batch_alter_table("analyses") as batch:
        batch.drop_index("ix_analyses_schedule_id")
        batch.drop_column("schedule_id")

    op.drop_index("ix_schedules_active", table_name="schedules")
    op.drop_index("ix_schedules_ticker", table_name="schedules")
    op.drop_table("schedules")

    op.drop_index("ix_holdings_ticker", table_name="holdings")
    op.drop_constraint("uq_holdings_ticker", "holdings", type_="unique")
    op.drop_table("holdings")
```

- [ ] **Step 8: 테스트 통과 확인**

Run: `uv run pytest tests/web/test_models_holding.py tests/web/test_models_schedule.py -v`
Expected: 3 passed.

- [ ] **Step 9: alembic up/down/up 검증**

Run:

```bash
rm -f /tmp/m3_mig.db
WEB_DATABASE_URL=sqlite:////tmp/m3_mig.db uv run alembic upgrade head
WEB_DATABASE_URL=sqlite:////tmp/m3_mig.db uv run alembic downgrade base
WEB_DATABASE_URL=sqlite:////tmp/m3_mig.db uv run alembic upgrade head
```

Expected: 모든 명령 에러 없이 종료.

- [ ] **Step 10: 커밋**

```bash
git add tradingagents_web/models/holding.py tradingagents_web/models/schedule.py \
    tradingagents_web/models/analysis.py tradingagents_web/models/__init__.py \
    migrations/versions/0003_holdings_schedules.py \
    tests/web/test_models_holding.py tests/web/test_models_schedule.py
git commit -m "feat(web): add Holding/Schedule models + 0003 migration"
```

---

## Task 2: Pydantic 스키마 (holdings, schedules, prices)

**Files:**
- Create: `tradingagents_web/schemas/holding.py`
- Create: `tradingagents_web/schemas/schedule.py`
- Create: `tradingagents_web/schemas/price.py`
- Modify: `tradingagents_web/schemas/__init__.py`
- Modify: `tradingagents_web/schemas/analysis.py` (add `schedule_id`)
- Create: `tests/web/test_schemas_holding.py`
- Create: `tests/web/test_schemas_schedule.py`

- [ ] **Step 1: 실패하는 holding 스키마 테스트 작성**

`tests/web/test_schemas_holding.py`:

```python
"""Tests for Pydantic schemas under schemas/holding.py."""
import pytest

from tradingagents_web.schemas.holding import HoldingCreate, HoldingUpdate


def test_holding_create_normalizes_ticker():
    h = HoldingCreate(ticker="aapl", qty=10, avg_cost=150.0)
    assert h.ticker == "AAPL"


def test_holding_create_rejects_blank_ticker():
    with pytest.raises(ValueError):
        HoldingCreate(ticker="   ", qty=1, avg_cost=1.0)


def test_holding_create_rejects_negative_qty():
    with pytest.raises(ValueError):
        HoldingCreate(ticker="AAPL", qty=-1, avg_cost=1.0)


def test_holding_update_partial():
    u = HoldingUpdate(monitor_enabled=True)
    assert u.monitor_enabled is True
    assert u.qty is None
```

- [ ] **Step 2: 실패하는 schedule 스키마 테스트 작성**

`tests/web/test_schemas_schedule.py`:

```python
"""Tests for Pydantic schemas under schemas/schedule.py."""
import pytest

from tradingagents_web.schemas.schedule import ScheduleCreate, SchedulePreset


def test_schedule_create_validates_cron():
    s = ScheduleCreate(
        name="daily",
        ticker="aapl",
        cron_expr="30 16 * * 1-5",
        preset=SchedulePreset(analysts=["market"], debate_rounds=1),
    )
    assert s.ticker == "AAPL"


def test_schedule_create_rejects_bad_cron():
    with pytest.raises(ValueError):
        ScheduleCreate(
            name="bad",
            ticker="AAPL",
            cron_expr="not a cron",
            preset=SchedulePreset(analysts=["market"], debate_rounds=1),
        )


def test_schedule_preset_rejects_unknown_analyst():
    with pytest.raises(ValueError):
        SchedulePreset(analysts=["bogus"], debate_rounds=1)
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `uv run pytest tests/web/test_schemas_holding.py tests/web/test_schemas_schedule.py -v`
Expected: ImportError.

- [ ] **Step 4: Holding 스키마 작성**

`tradingagents_web/schemas/holding.py`:

```python
"""Pydantic schemas for the holdings API."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HoldingCreate(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=16)
    qty: float = Field(..., ge=0)
    avg_cost: float = Field(..., ge=0)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("ticker")
    @classmethod
    def _normalize(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("ticker must not be blank")
        return v


class HoldingUpdate(BaseModel):
    qty: float | None = Field(default=None, ge=0)
    avg_cost: float | None = Field(default=None, ge=0)
    monitor_enabled: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)


class HoldingItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    qty: float
    avg_cost: float
    monitor_enabled: bool
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class HoldingListResponse(BaseModel):
    items: list[HoldingItem]
```

- [ ] **Step 5: Schedule 스키마 작성**

`tradingagents_web/schemas/schedule.py`:

```python
"""Pydantic schemas for the schedules API."""
from datetime import datetime
from typing import Literal

from croniter import croniter
from pydantic import BaseModel, ConfigDict, Field, field_validator

VALID_ANALYSTS = {"market", "social", "news", "fundamentals"}


class SchedulePreset(BaseModel):
    analysts: list[str] = Field(..., min_length=1)
    debate_rounds: int = Field(default=1, ge=1, le=5)
    llm_provider: str | None = None
    llm_deep_model: str | None = None
    llm_quick_model: str | None = None

    @field_validator("analysts")
    @classmethod
    def _check_analysts(cls, v: list[str]) -> list[str]:
        bad = [a for a in v if a not in VALID_ANALYSTS]
        if bad:
            raise ValueError(f"unknown analysts: {bad}")
        return v


def _validate_cron(value: str) -> str:
    value = value.strip()
    if not croniter.is_valid(value):
        raise ValueError(f"invalid cron expression: {value!r}")
    return value


class ScheduleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    ticker: str = Field(..., min_length=1, max_length=16)
    cron_expr: str
    preset: SchedulePreset
    active: bool = True

    @field_validator("ticker")
    @classmethod
    def _norm_ticker(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("ticker must not be blank")
        return v

    @field_validator("cron_expr")
    @classmethod
    def _check_cron(cls, v: str) -> str:
        return _validate_cron(v)


class ScheduleUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    cron_expr: str | None = None
    preset: SchedulePreset | None = None
    active: bool | None = None

    @field_validator("cron_expr")
    @classmethod
    def _check_cron(cls, v: str | None) -> str | None:
        return _validate_cron(v) if v is not None else None


class ScheduleItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    ticker: str
    cron_expr: str
    preset: dict
    active: bool
    last_run: datetime | None
    next_run: datetime | None
    source: Literal["user", "holding"]
    holding_id: int | None
    created_at: datetime


class ScheduleListResponse(BaseModel):
    items: list[ScheduleItem]
```

- [ ] **Step 6: Price 스키마 작성**

`tradingagents_web/schemas/price.py`:

```python
"""Pydantic schemas for the prices API."""
from datetime import date

from pydantic import BaseModel


class PricePoint(BaseModel):
    date: date
    close: float


class PriceHistoryResponse(BaseModel):
    ticker: str
    points: list[PricePoint]
    last_close: float | None
```

- [ ] **Step 7: schemas/__init__.py + analysis.py 갱신**

`tradingagents_web/schemas/__init__.py`:

```python
"""Pydantic schema exports."""
from tradingagents_web.schemas.analysis import (
    AnalysisCreateRequest,
    AnalysisCreateResponse,
    AnalysisDetail,
    AnalysisListItem,
    AnalysisListResponse,
)
from tradingagents_web.schemas.holding import (
    HoldingCreate,
    HoldingItem,
    HoldingListResponse,
    HoldingUpdate,
)
from tradingagents_web.schemas.price import PriceHistoryResponse, PricePoint
from tradingagents_web.schemas.schedule import (
    ScheduleCreate,
    ScheduleItem,
    ScheduleListResponse,
    SchedulePreset,
    ScheduleUpdate,
)

__all__ = [
    "AnalysisCreateRequest",
    "AnalysisCreateResponse",
    "AnalysisDetail",
    "AnalysisListItem",
    "AnalysisListResponse",
    "HoldingCreate",
    "HoldingItem",
    "HoldingListResponse",
    "HoldingUpdate",
    "PriceHistoryResponse",
    "PricePoint",
    "ScheduleCreate",
    "ScheduleItem",
    "ScheduleListResponse",
    "SchedulePreset",
    "ScheduleUpdate",
]
```

`tradingagents_web/schemas/analysis.py` — `AnalysisListItem`과 `AnalysisDetail`에 `schedule_id` 추가:

```python
class AnalysisListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    ticker: str
    analysis_date: date
    status: Status
    decision: Decision | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    created_at: datetime | str
    completed_at: datetime | None = None
    schedule_id: int | None = None
```

(같은 한 줄을 `AnalysisDetail`에도 추가.)

- [ ] **Step 8: pyproject.toml에 croniter 추가**

`pyproject.toml` 의존성에 추가 (이미 `apscheduler`도 추후 task에서 들어가므로 함께):

```toml
"apscheduler>=3.10",
"croniter>=2.0",
```

Run:

```bash
uv sync
```

- [ ] **Step 9: 테스트 통과 확인**

Run: `uv run pytest tests/web/test_schemas_holding.py tests/web/test_schemas_schedule.py tests/web/test_schemas_analysis.py -v`
Expected: 모두 pass.

- [ ] **Step 10: 커밋**

```bash
git add tradingagents_web/schemas/ tests/web/test_schemas_holding.py tests/web/test_schemas_schedule.py pyproject.toml uv.lock
git commit -m "feat(web): add Pydantic schemas for holdings/schedules/prices"
```

---

## Task 3: 가격 서비스 (yfinance + 5분 TTL 캐시)

**Files:**
- Create: `tradingagents_web/services/prices.py`
- Create: `tests/web/test_prices_service.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/web/test_prices_service.py`:

```python
"""Tests for the price service (yfinance wrapper + TTL cache)."""
from datetime import date, datetime, timezone

import pytest

from tradingagents_web.services import prices as svc


@pytest.fixture(autouse=True)
def _clear_cache():
    svc._CACHE.clear()
    yield
    svc._CACHE.clear()


def test_get_history_returns_points(monkeypatch):
    captured = {"calls": 0}

    def fake_download(ticker, start, end, interval, progress=False, auto_adjust=True):
        captured["calls"] += 1
        import pandas as pd
        idx = pd.to_datetime(["2026-04-21", "2026-04-22"])
        return pd.DataFrame({"Close": [180.0, 181.5]}, index=idx)

    monkeypatch.setattr(svc, "_yf_download", fake_download)

    out = svc.get_price_history("aapl", days=5)
    assert out.ticker == "AAPL"
    assert len(out.points) == 2
    assert out.last_close == 181.5
    assert captured["calls"] == 1

    # Second call within TTL window does not re-download.
    again = svc.get_price_history("AAPL", days=5)
    assert again.last_close == 181.5
    assert captured["calls"] == 1


def test_get_history_empty_returns_no_last_close(monkeypatch):
    def fake_download(*a, **kw):
        import pandas as pd
        return pd.DataFrame({"Close": []}, index=pd.to_datetime([]))

    monkeypatch.setattr(svc, "_yf_download", fake_download)
    out = svc.get_price_history("XYZ", days=5)
    assert out.points == []
    assert out.last_close is None
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/web/test_prices_service.py -v`
Expected: ImportError.

- [ ] **Step 3: 가격 서비스 구현**

`tradingagents_web/services/prices.py`:

```python
"""yfinance wrapper with a small TTL cache.

We store at most ~32 entries (more than enough for personal use). Each entry
key is ``(TICKER, days)`` and value is ``(expires_at_unix, PriceHistoryResponse)``.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from tradingagents_web.schemas.price import PriceHistoryResponse, PricePoint

logger = logging.getLogger(__name__)

_TTL_SECONDS = 300  # 5 minutes
_CACHE: dict[tuple[str, int], tuple[float, PriceHistoryResponse]] = {}


def _yf_download(ticker, start, end, interval, progress=False, auto_adjust=True):
    """Indirection so tests can monkeypatch yfinance.download cleanly."""
    import yfinance as yf

    return yf.download(
        ticker,
        start=start,
        end=end,
        interval=interval,
        progress=progress,
        auto_adjust=auto_adjust,
    )


def get_price_history(ticker: str, days: int = 90) -> PriceHistoryResponse:
    """Return up to ``days`` of daily close prices for ``ticker``.

    Args:
        ticker: Stock symbol (case-insensitive).
        days: Look-back window in calendar days.

    Returns:
        PriceHistoryResponse with daily PricePoints sorted ascending.
    """
    key = (ticker.strip().upper(), days)
    now = time.time()
    cached = _CACHE.get(key)
    if cached and cached[0] > now:
        return cached[1]

    end = datetime.now(timezone.utc).date() + timedelta(days=1)
    start = end - timedelta(days=days)
    try:
        df = _yf_download(key[0], start=start, end=end, interval="1d")
    except Exception:  # noqa: BLE001
        logger.exception("yfinance download failed for %s", key[0])
        df = None

    points: list[PricePoint] = []
    last_close: float | None = None
    if df is not None and len(df) > 0 and "Close" in df.columns:
        for ts, row in df.iterrows():
            close = float(row["Close"])
            points.append(PricePoint(date=ts.date(), close=close))
        last_close = points[-1].close if points else None

    response = PriceHistoryResponse(
        ticker=key[0],
        points=points,
        last_close=last_close,
    )
    _CACHE[key] = (now + _TTL_SECONDS, response)
    return response


def clear_cache() -> None:
    """Drop the in-memory cache (used by tests / settings reload)."""
    _CACHE.clear()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/web/test_prices_service.py -v`
Expected: 2 passed.

- [ ] **Step 5: 커밋**

```bash
git add tradingagents_web/services/prices.py tests/web/test_prices_service.py
git commit -m "feat(web): add price service with 5min TTL cache"
```

---

## Task 4: APScheduler 서비스 + lifespan 통합

**Files:**
- Create: `tradingagents_web/services/scheduler.py`
- Modify: `tradingagents_web/config.py`
- Create: `tests/web/test_scheduler_service.py`

- [ ] **Step 1: config 변경사항 테스트 작성**

`tests/web/test_config.py` 끝에 추가 (기존 테스트 파일 보존):

```python
def test_settings_includes_schedule_tz_default():
    from tradingagents_web.config import Settings

    s = Settings()
    assert s.schedule_tz == "America/New_York"
    assert s.scheduler_grace_seconds == 60
```

- [ ] **Step 2: scheduler 서비스 테스트 작성**

`tests/web/test_scheduler_service.py`:

```python
"""Tests for SchedulerService."""
import asyncio
from datetime import datetime, timezone

import pytest

from tradingagents_web.models import Schedule
from tradingagents_web.services.scheduler import SchedulerService


@pytest.fixture()
def svc():
    s = SchedulerService(tz="UTC")
    yield s
    if s.is_running():
        s.shutdown()


def test_start_and_shutdown(svc):
    svc.start()
    assert svc.is_running() is True
    svc.shutdown()
    assert svc.is_running() is False


def test_register_schedule_creates_apjob(svc, app_with_test_db):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        sched = Schedule(
            name="d",
            ticker="AAPL",
            cron_expr="0 9 * * *",
            preset={"analysts": ["market"], "debate_rounds": 1},
            active=True,
        )
        db.add(sched)
        db.commit()
        db.refresh(sched)
    finally:
        db.close()

    triggered: list[int] = []

    async def fake_trigger(schedule_id: int) -> None:
        triggered.append(schedule_id)

    svc.set_trigger_callback(fake_trigger)
    svc.start()
    svc.register(sched)
    job = svc.get_job(sched.id)
    assert job is not None
    assert job.next_run_time is not None


def test_unregister_drops_apjob(svc):
    svc.start()
    sched = type("S", (), {"id": 99, "cron_expr": "0 9 * * *", "active": True})()
    # Manually add a noop job to exercise unregister path
    svc.scheduler.add_job(lambda: None, "cron", id=svc._job_id(99), minute=0, hour=9)
    svc.unregister(99)
    assert svc.get_job(99) is None
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `uv run pytest tests/web/test_scheduler_service.py tests/web/test_config.py -v`
Expected: ImportError 또는 AttributeError.

- [ ] **Step 4: config.py 갱신**

`tradingagents_web/config.py` — Settings에 두 필드 추가:

```python
    # Scheduler
    schedule_tz: str = "America/New_York"
    scheduler_grace_seconds: int = 60
```

- [ ] **Step 5: SchedulerService 구현**

`tradingagents_web/services/scheduler.py`:

```python
"""APScheduler wrapper.

The DB ``schedules`` table is the source of truth. On startup,
:meth:`SchedulerService.bootstrap` reads all ``active=True`` rows and
registers them with the in-process AsyncIOScheduler. CRUD endpoints
keep the scheduler in sync via :meth:`register` / :meth:`unregister`.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from apscheduler.job import Job
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session as OrmSession

from tradingagents_web.models import Schedule

logger = logging.getLogger(__name__)

TriggerCallback = Callable[[int], Awaitable[None]]


class SchedulerService:
    """Owns a single AsyncIOScheduler instance."""

    def __init__(self, tz: str = "America/New_York", grace_seconds: int = 60) -> None:
        self.scheduler = AsyncIOScheduler(
            timezone=tz,
            job_defaults={
                "coalesce": True,
                "misfire_grace_time": grace_seconds,
                "max_instances": 1,
            },
        )
        self._tz = tz
        self._on_trigger: TriggerCallback | None = None

    def set_trigger_callback(self, cb: TriggerCallback) -> None:
        """Wire the coroutine that runs when any schedule fires."""
        self._on_trigger = cb

    def start(self) -> None:
        if not self.scheduler.running:
            self.scheduler.start()

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def is_running(self) -> bool:
        return self.scheduler.running

    @staticmethod
    def _job_id(schedule_id: int) -> str:
        return f"sched-{schedule_id}"

    def get_job(self, schedule_id: int) -> Job | None:
        return self.scheduler.get_job(self._job_id(schedule_id))

    async def _fire(self, schedule_id: int) -> None:
        if self._on_trigger is None:
            logger.warning("Scheduler fired with no trigger callback (id=%s)", schedule_id)
            return
        try:
            await self._on_trigger(schedule_id)
        except Exception:  # noqa: BLE001
            logger.exception("Scheduler trigger callback failed (id=%s)", schedule_id)

    def register(self, schedule: Schedule) -> None:
        """Add or replace the APScheduler job for ``schedule``."""
        if not schedule.active:
            self.unregister(schedule.id)
            return
        trigger = CronTrigger.from_crontab(schedule.cron_expr, timezone=self._tz)
        self.scheduler.add_job(
            self._fire,
            trigger=trigger,
            id=self._job_id(schedule.id),
            args=[schedule.id],
            replace_existing=True,
        )

    def unregister(self, schedule_id: int) -> None:
        try:
            self.scheduler.remove_job(self._job_id(schedule_id))
        except Exception:  # noqa: BLE001
            pass  # idempotent

    def next_run(self, schedule_id: int) -> datetime | None:
        job = self.get_job(schedule_id)
        return job.next_run_time if job else None

    def bootstrap(self, db: OrmSession) -> None:
        """Register every ``active=True`` schedule from DB into the scheduler."""
        rows = db.query(Schedule).filter(Schedule.active.is_(True)).all()
        for r in rows:
            self.register(r)
        logger.info("Bootstrap registered %d schedules", len(rows))


_singleton: SchedulerService | None = None


def get_scheduler() -> SchedulerService:
    """Module-global accessor (lifespan creates it on app startup)."""
    if _singleton is None:
        raise RuntimeError("SchedulerService is not initialized")
    return _singleton


def set_scheduler(svc: SchedulerService | None) -> None:
    """Inject (or clear) the global scheduler. Used by lifespan + tests."""
    global _singleton
    _singleton = svc
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `uv run pytest tests/web/test_scheduler_service.py tests/web/test_config.py -v`
Expected: 모두 pass.

- [ ] **Step 7: 커밋**

```bash
git add tradingagents_web/services/scheduler.py tradingagents_web/config.py \
    tests/web/test_scheduler_service.py tests/web/test_config.py
git commit -m "feat(web): add APScheduler service wrapper"
```

---

## Task 5: `start_analysis_run()` 헬퍼 추출 + `auto_runner`

**Goal:** M2 `runs.py`의 "분석 row 생성 + 백그라운드 task 등록" 로직을 함수로 빼서, 스케줄러도 같은 경로로 분석을 시작할 수 있게 한다.

**Files:**
- Modify: `tradingagents_web/api/runs.py`
- Create: `tradingagents_web/services/auto_runner.py`
- Create: `tests/web/test_auto_runner.py`

- [ ] **Step 1: auto_runner 테스트 작성**

`tests/web/test_auto_runner.py`:

```python
"""Tests for services.auto_runner.trigger_run."""
import asyncio
from datetime import date, datetime, timezone

import pytest

from tradingagents_web.models import Analysis, Schedule
from tradingagents_web.services.auto_runner import trigger_run
from tradingagents_web.services.event_bus import reset_event_bus


@pytest.fixture(autouse=True)
def _reset_bus():
    reset_event_bus()
    yield
    reset_event_bus()


def test_trigger_run_creates_analysis_row_and_updates_schedule(
    monkeypatch, app_with_test_db
):
    monkeypatch.setenv("WEB_FAKE_RUNNER", "true")
    monkeypatch.setenv("WEB_FAKE_RUNNER_DELAY_SECONDS", "0")

    _, TestSessionLocal = app_with_test_db
    from tradingagents_web.api import runs as runs_api
    runs_api.set_background_session_factory(TestSessionLocal)

    db = TestSessionLocal()
    try:
        sched = Schedule(
            name="auto",
            ticker="AAPL",
            cron_expr="0 9 * * *",
            preset={"analysts": ["market", "news"], "debate_rounds": 1},
            active=True,
        )
        db.add(sched)
        db.commit()
        db.refresh(sched)
        sid = sched.id
    finally:
        db.close()

    asyncio.get_event_loop().run_until_complete(
        trigger_run(sid, session_factory=TestSessionLocal)
    )

    db = TestSessionLocal()
    try:
        rows = db.query(Analysis).filter_by(schedule_id=sid).all()
        assert len(rows) == 1
        assert rows[0].ticker == "AAPL"
        assert rows[0].status in ("running", "completed")
        # last_run was stamped
        sched = db.query(Schedule).get(sid)
        assert sched.last_run is not None
    finally:
        db.close()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/web/test_auto_runner.py -v`
Expected: ImportError.

- [ ] **Step 3: `start_analysis_run` 헬퍼 추출**

`tradingagents_web/api/runs.py` — 새 함수를 모듈 함수로 추가하고 `create_run`이 호출하도록 변경:

기존 `_resolve_models` 다음, `_execute_and_persist` 위에 삽입:

```python
def start_analysis_run(
    db: OrmSession,
    *,
    ticker: str,
    analysis_date: "date",
    analysts: list[str],
    debate_rounds: int,
    llm_provider: str,
    llm_deep_model: str,
    llm_quick_model: str,
    schedule_id: int | None = None,
) -> str:
    """Persist a fresh analyses row and kick off the background runner.

    Shared by ``POST /api/runs`` and the scheduler-driven auto runner.

    Args:
        db: SQLAlchemy session for inserting the analyses row.
        ticker: Normalized ticker symbol (uppercased).
        analysis_date: Trading date the analysis targets.
        analysts: List of analyst roles.
        debate_rounds: Bull/bear debate rounds.
        llm_provider: LLM provider id.
        llm_deep_model: Deep model id.
        llm_quick_model: Quick model id.
        schedule_id: If non-None, links the run to a schedule.

    Returns:
        The new ``run_id`` UUID string.
    """
    run_id = str(uuid.uuid4())
    row = Analysis(
        run_id=run_id,
        ticker=ticker,
        analysis_date=analysis_date,
        status="running",
        llm_provider=llm_provider,
        llm_deep_model=llm_deep_model,
        llm_quick_model=llm_quick_model,
        debate_rounds=debate_rounds,
        analysts=analysts,
        schedule_id=schedule_id,
    )
    db.add(row)
    db.commit()

    request = RunRequest(
        run_id=run_id,
        ticker=ticker,
        analysis_date=analysis_date,
        analysts=analysts,
        debate_rounds=debate_rounds,
        llm_provider=llm_provider,
        llm_deep_model=llm_deep_model,
        llm_quick_model=llm_quick_model,
    )
    task = asyncio.create_task(_execute_and_persist(run_id, request))
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return run_id
```

`create_run` 본문은 위 헬퍼를 사용하도록 단순화:

```python
@router.post(
    "",
    response_model=AnalysisCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_run(
    payload: AnalysisCreateRequest,
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> AnalysisCreateResponse:
    provider, deep, quick = _resolve_models(payload)
    run_id = start_analysis_run(
        db,
        ticker=payload.ticker,
        analysis_date=payload.analysis_date,
        analysts=payload.analysts,
        debate_rounds=payload.debate_rounds,
        llm_provider=provider,
        llm_deep_model=deep,
        llm_quick_model=quick,
    )
    return AnalysisCreateResponse(run_id=run_id)
```

- [ ] **Step 4: 기존 runs API 회귀 확인**

Run: `uv run pytest tests/web/test_runs_api.py -v`
Expected: 모두 pass (기존 테스트 그대로 동작).

- [ ] **Step 5: auto_runner 구현**

`tradingagents_web/services/auto_runner.py`:

```python
"""Bridge between APScheduler firing and the runs API.

When a schedule fires the SchedulerService calls :func:`trigger_run`
with the schedule_id. We open a fresh DB session (we are off the
request lifecycle here), look up the schedule, and reuse
``runs.start_analysis_run`` so the persistence and event-bus paths
are identical to the user-initiated POST /api/runs flow.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy.orm import Session as OrmSession

from tradingagents_web.config import Settings
from tradingagents_web.db import SessionLocal
from tradingagents_web.models import Schedule

logger = logging.getLogger(__name__)


async def trigger_run(
    schedule_id: int,
    *,
    session_factory: Callable[[], OrmSession] = SessionLocal,
) -> str | None:
    """Fire-and-forget: load the schedule and start an analysis run.

    Args:
        schedule_id: Schedule row id.
        session_factory: Zero-arg factory returning a SQLAlchemy session
            (overridden by tests).

    Returns:
        New run_id if started, None if the schedule was not found or inactive.
    """
    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents_web.api.runs import start_analysis_run

    db = session_factory()
    try:
        sched = db.query(Schedule).get(schedule_id)
        if sched is None:
            logger.warning("Schedule %s not found at fire time", schedule_id)
            return None
        if not sched.active:
            logger.info("Schedule %s is inactive — skipping fire", schedule_id)
            return None

        preset = sched.preset or {}
        analysts = preset.get("analysts") or [
            "market",
            "social",
            "news",
            "fundamentals",
        ]
        debate = int(preset.get("debate_rounds") or 1)
        provider = preset.get("llm_provider") or DEFAULT_CONFIG["llm_provider"]
        deep = preset.get("llm_deep_model") or DEFAULT_CONFIG["deep_think_llm"]
        quick = preset.get("llm_quick_model") or DEFAULT_CONFIG["quick_think_llm"]

        run_id = start_analysis_run(
            db,
            ticker=sched.ticker,
            analysis_date=datetime.now(timezone.utc).date(),
            analysts=analysts,
            debate_rounds=debate,
            llm_provider=provider,
            llm_deep_model=deep,
            llm_quick_model=quick,
            schedule_id=sched.id,
        )
        sched.last_run = datetime.now(timezone.utc)
        db.commit()
        logger.info("Schedule %s fired -> run %s", schedule_id, run_id)
        return run_id
    finally:
        db.close()
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `uv run pytest tests/web/test_auto_runner.py -v`
Expected: 1 passed.

- [ ] **Step 7: 커밋**

```bash
git add tradingagents_web/api/runs.py tradingagents_web/services/auto_runner.py tests/web/test_auto_runner.py
git commit -m "feat(web): extract start_analysis_run + add auto_runner bridge"
```

---

## Task 6: `holdings_sync` (auto-monitor 토글 ↔ schedules 동기화)

**Goal:** `holdings.monitor_enabled` 토글에 따라 동일 ticker의 `source="holding"` schedule 행을 자동 생성/삭제. CRUD API에서 호출되는 순수 함수.

**Files:**
- Create: `tradingagents_web/services/holdings_sync.py`
- Create: `tests/web/test_holdings_sync.py`

- [ ] **Step 1: 테스트 작성**

`tests/web/test_holdings_sync.py`:

```python
"""Tests for holdings_sync.sync_holding_monitor."""
from tradingagents_web.models import Holding, Schedule
from tradingagents_web.services.holdings_sync import (
    DEFAULT_MONITOR_CRON,
    sync_holding_monitor,
)


def test_enable_creates_schedule(app_with_test_db):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        h = Holding(ticker="AAPL", qty=1, avg_cost=10, monitor_enabled=True)
        db.add(h)
        db.commit()
        db.refresh(h)
        sync_holding_monitor(db, h)
        db.commit()
        rows = db.query(Schedule).filter_by(holding_id=h.id, source="holding").all()
        assert len(rows) == 1
        assert rows[0].cron_expr == DEFAULT_MONITOR_CRON
        assert rows[0].active is True
    finally:
        db.close()


def test_disable_removes_schedule(app_with_test_db):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        h = Holding(ticker="NVDA", qty=1, avg_cost=10, monitor_enabled=True)
        db.add(h)
        db.commit()
        db.refresh(h)
        sync_holding_monitor(db, h)
        db.commit()
        h.monitor_enabled = False
        sync_holding_monitor(db, h)
        db.commit()
        rows = db.query(Schedule).filter_by(holding_id=h.id, source="holding").all()
        assert rows == []
    finally:
        db.close()


def test_enable_idempotent(app_with_test_db):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        h = Holding(ticker="MSFT", qty=1, avg_cost=10, monitor_enabled=True)
        db.add(h)
        db.commit()
        db.refresh(h)
        sync_holding_monitor(db, h)
        sync_holding_monitor(db, h)
        db.commit()
        rows = db.query(Schedule).filter_by(holding_id=h.id, source="holding").all()
        assert len(rows) == 1
    finally:
        db.close()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/web/test_holdings_sync.py -v`
Expected: ImportError.

- [ ] **Step 3: 구현**

`tradingagents_web/services/holdings_sync.py`:

```python
"""Keep an auto-managed Schedule row in sync with Holding.monitor_enabled."""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session as OrmSession

from tradingagents_web.models import Holding, Schedule

logger = logging.getLogger(__name__)

DEFAULT_MONITOR_CRON = "30 16 * * 1-5"  # weekdays at 16:30 in WEB_SCHEDULE_TZ
DEFAULT_PRESET = {
    "analysts": ["market", "social", "news", "fundamentals"],
    "debate_rounds": 1,
}


def sync_holding_monitor(db: OrmSession, holding: Holding) -> Schedule | None:
    """Create, activate, or remove the auto schedule tied to ``holding``.

    The function must be followed by ``db.commit()`` by the caller. It does
    not commit so the caller can register/unregister the APScheduler job in
    the same DB transaction.

    Returns:
        The Schedule row if monitor is enabled, otherwise None.
    """
    existing = (
        db.query(Schedule)
        .filter_by(holding_id=holding.id, source="holding")
        .one_or_none()
    )
    if holding.monitor_enabled:
        if existing is None:
            existing = Schedule(
                name=f"Auto monitor {holding.ticker}",
                ticker=holding.ticker,
                cron_expr=DEFAULT_MONITOR_CRON,
                preset=dict(DEFAULT_PRESET),
                active=True,
                source="holding",
                holding_id=holding.id,
            )
            db.add(existing)
        else:
            existing.active = True
            existing.ticker = holding.ticker
        return existing

    if existing is not None:
        db.delete(existing)
    return None
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/web/test_holdings_sync.py -v`
Expected: 3 passed.

- [ ] **Step 5: 커밋**

```bash
git add tradingagents_web/services/holdings_sync.py tests/web/test_holdings_sync.py
git commit -m "feat(web): add holdings_sync service for auto-monitor toggle"
```

---

## Task 7: Holdings CRUD API

**Files:**
- Create: `tradingagents_web/api/holdings.py`
- Create: `tests/web/test_holdings_api.py`

- [ ] **Step 1: 테스트 작성**

`tests/web/test_holdings_api.py`:

```python
"""API tests for /api/holdings."""
import pytest

from tradingagents_web.auth import create_session
from tradingagents_web.config import Settings
from tradingagents_web.models import Holding, Schedule, User

_settings = Settings()


def _login(app_with_test_db, client):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        user = User(password_hash="x")
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_session(db, user.id)
    finally:
        db.close()
    client.cookies.set(_settings.session_cookie_name, token)
    return client


def test_list_holdings_requires_auth(client):
    r = client.get("/api/holdings")
    assert r.status_code == 401


def test_create_then_list_holding(app_with_test_db, client):
    client = _login(app_with_test_db, client)
    r = client.post(
        "/api/holdings",
        headers={"X-Requested-With": "fetch"},
        json={"ticker": "aapl", "qty": 10, "avg_cost": 150.0},
    )
    assert r.status_code == 201, r.text
    item = r.json()
    assert item["ticker"] == "AAPL"
    assert item["monitor_enabled"] is False

    r = client.get("/api/holdings")
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1


def test_update_holding_qty(app_with_test_db, client):
    client = _login(app_with_test_db, client)
    r = client.post(
        "/api/holdings",
        headers={"X-Requested-With": "fetch"},
        json={"ticker": "AAPL", "qty": 1, "avg_cost": 100},
    )
    hid = r.json()["id"]
    r2 = client.patch(
        f"/api/holdings/{hid}",
        headers={"X-Requested-With": "fetch"},
        json={"qty": 5},
    )
    assert r2.status_code == 200
    assert r2.json()["qty"] == 5


def test_toggle_monitor_creates_schedule(app_with_test_db, client):
    client = _login(app_with_test_db, client)
    r = client.post(
        "/api/holdings",
        headers={"X-Requested-With": "fetch"},
        json={"ticker": "MSFT", "qty": 1, "avg_cost": 100},
    )
    hid = r.json()["id"]
    r2 = client.patch(
        f"/api/holdings/{hid}",
        headers={"X-Requested-With": "fetch"},
        json={"monitor_enabled": True},
    )
    assert r2.status_code == 200
    assert r2.json()["monitor_enabled"] is True

    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        rows = db.query(Schedule).filter_by(holding_id=hid, source="holding").all()
        assert len(rows) == 1
        assert rows[0].active is True
    finally:
        db.close()

    r3 = client.patch(
        f"/api/holdings/{hid}",
        headers={"X-Requested-With": "fetch"},
        json={"monitor_enabled": False},
    )
    assert r3.status_code == 200
    db = TestSessionLocal()
    try:
        rows = db.query(Schedule).filter_by(holding_id=hid, source="holding").all()
        assert rows == []
    finally:
        db.close()


def test_delete_holding(app_with_test_db, client):
    client = _login(app_with_test_db, client)
    r = client.post(
        "/api/holdings",
        headers={"X-Requested-With": "fetch"},
        json={"ticker": "TSLA", "qty": 1, "avg_cost": 200},
    )
    hid = r.json()["id"]
    r2 = client.delete(
        f"/api/holdings/{hid}",
        headers={"X-Requested-With": "fetch"},
    )
    assert r2.status_code == 204
    r3 = client.get("/api/holdings")
    assert r3.json()["items"] == []


def test_create_duplicate_ticker_returns_409(app_with_test_db, client):
    client = _login(app_with_test_db, client)
    payload = {"ticker": "AAPL", "qty": 1, "avg_cost": 100}
    r1 = client.post(
        "/api/holdings",
        headers={"X-Requested-With": "fetch"},
        json=payload,
    )
    assert r1.status_code == 201
    r2 = client.post(
        "/api/holdings",
        headers={"X-Requested-With": "fetch"},
        json=payload,
    )
    assert r2.status_code == 409
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/web/test_holdings_api.py -v`
Expected: 404 / ImportError (router 미등록).

- [ ] **Step 3: 구현**

`tradingagents_web/api/holdings.py`:

```python
"""Holdings CRUD API."""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as OrmSession

from tradingagents_web.auth import get_current_user, require_xhr
from tradingagents_web.db import get_db
from tradingagents_web.models import Holding, User
from tradingagents_web.schemas.holding import (
    HoldingCreate,
    HoldingItem,
    HoldingListResponse,
    HoldingUpdate,
)
from tradingagents_web.services import scheduler as scheduler_module
from tradingagents_web.services.holdings_sync import sync_holding_monitor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/holdings", tags=["holdings"])


@router.get("", response_model=HoldingListResponse)
def list_holdings(
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> HoldingListResponse:
    rows = db.query(Holding).order_by(Holding.ticker.asc()).all()
    return HoldingListResponse(items=[HoldingItem.model_validate(r) for r in rows])


@router.post(
    "",
    response_model=HoldingItem,
    status_code=status.HTTP_201_CREATED,
)
def create_holding(
    payload: HoldingCreate,
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> HoldingItem:
    h = Holding(
        ticker=payload.ticker,
        qty=payload.qty,
        avg_cost=payload.avg_cost,
        notes=payload.notes,
    )
    db.add(h)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="ticker already exists")
    db.refresh(h)
    return HoldingItem.model_validate(h)


@router.patch("/{holding_id}", response_model=HoldingItem)
def update_holding(
    holding_id: int,
    payload: HoldingUpdate,
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> HoldingItem:
    h = db.query(Holding).get(holding_id)
    if h is None:
        raise HTTPException(status_code=404, detail="holding not found")

    monitor_changed = False
    if payload.qty is not None:
        h.qty = payload.qty
    if payload.avg_cost is not None:
        h.avg_cost = payload.avg_cost
    if payload.notes is not None:
        h.notes = payload.notes
    if payload.monitor_enabled is not None and payload.monitor_enabled != h.monitor_enabled:
        h.monitor_enabled = payload.monitor_enabled
        monitor_changed = True

    sched = None
    if monitor_changed:
        sched = sync_holding_monitor(db, h)
    db.commit()
    db.refresh(h)

    if monitor_changed:
        try:
            sch_svc = scheduler_module.get_scheduler()
        except RuntimeError:
            sch_svc = None
        if sch_svc is not None:
            if sched is not None:
                db.refresh(sched)
                sch_svc.register(sched)
            else:
                # Removed: find by holding_id is no longer in DB; nothing to unregister
                # because we already deleted the Schedule row. APScheduler job IDs are
                # keyed by schedule.id which we no longer have, so we rely on the
                # bootstrap path on next restart. For correctness, we'd need to look
                # up the prior schedule.id before deletion — handled below in next step.
                pass

    return HoldingItem.model_validate(h)


@router.delete("/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_holding(
    holding_id: int,
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> None:
    h = db.query(Holding).get(holding_id)
    if h is None:
        raise HTTPException(status_code=404, detail="holding not found")

    # Capture and remove tied schedule before deleting the holding row.
    h.monitor_enabled = False
    sync_holding_monitor(db, h)
    db.delete(h)
    db.commit()
    return None
```

> **Step 3.1: 스케줄러 unregister 보완.**
>
> `sync_holding_monitor`이 row를 삭제하기 전에 schedule.id를 캡처하고 endpoint에서 `unregister` 하도록 변경하는 것이 깔끔하다. 위 구현의 `update_holding` 분기 중 monitor=False 경로를 다음과 같이 보강:

`update_holding` 함수 내, `if monitor_changed:` 직전에 captured 변수를 추가하고 `sync_holding_monitor` 호출 시 이전 row id를 보존:

```python
    captured_old_schedule_id: int | None = None
    if payload.monitor_enabled is False and monitor_changed:
        old = (
            db.query(Schedule)
            .filter_by(holding_id=h.id, source="holding")
            .one_or_none()
        )
        captured_old_schedule_id = old.id if old else None

    sched = None
    if monitor_changed:
        sched = sync_holding_monitor(db, h)
    db.commit()
    db.refresh(h)

    if monitor_changed:
        try:
            sch_svc = scheduler_module.get_scheduler()
        except RuntimeError:
            sch_svc = None
        if sch_svc is not None:
            if sched is not None:
                db.refresh(sched)
                sch_svc.register(sched)
            elif captured_old_schedule_id is not None:
                sch_svc.unregister(captured_old_schedule_id)
```

`from tradingagents_web.models import Holding, Schedule, User`로 import 갱신.

- [ ] **Step 4: 라우터를 main.py에 등록**

(Task 10에서 일괄 처리하므로 여기서는 임시 등록.)

`tradingagents_web/main.py`의 `create_app`에 다음 한 줄 추가:

```python
    from tradingagents_web.api import holdings as holdings_api
    app.include_router(holdings_api.router)
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `uv run pytest tests/web/test_holdings_api.py -v`
Expected: 모두 pass.

> 참고: 이 테스트는 SchedulerService 없이 동작해야 하므로, `holdings.py`에서 `get_scheduler()`가 `RuntimeError`를 던질 때 안전하게 패스하는 분기를 이미 포함하고 있다.

- [ ] **Step 6: 커밋**

```bash
git add tradingagents_web/api/holdings.py tradingagents_web/main.py tests/web/test_holdings_api.py
git commit -m "feat(web): add holdings CRUD API"
```

---

## Task 8: Schedules CRUD API (+ run-now)

**Files:**
- Create: `tradingagents_web/api/schedules.py`
- Create: `tests/web/test_schedules_api.py`

- [ ] **Step 1: 테스트 작성**

`tests/web/test_schedules_api.py`:

```python
"""API tests for /api/schedules."""
import pytest

from tradingagents_web.auth import create_session
from tradingagents_web.config import Settings
from tradingagents_web.models import Schedule, User

_settings = Settings()


def _login(app_with_test_db, client):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        user = User(password_hash="x")
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_session(db, user.id)
    finally:
        db.close()
    client.cookies.set(_settings.session_cookie_name, token)
    return client


def test_list_schedules_empty(app_with_test_db, client):
    client = _login(app_with_test_db, client)
    r = client.get("/api/schedules")
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_create_schedule(app_with_test_db, client):
    client = _login(app_with_test_db, client)
    r = client.post(
        "/api/schedules",
        headers={"X-Requested-With": "fetch"},
        json={
            "name": "AAPL daily",
            "ticker": "aapl",
            "cron_expr": "30 16 * * 1-5",
            "preset": {"analysts": ["market"], "debate_rounds": 1},
        },
    )
    assert r.status_code == 201, r.text
    item = r.json()
    assert item["ticker"] == "AAPL"
    assert item["source"] == "user"


def test_create_schedule_invalid_cron(app_with_test_db, client):
    client = _login(app_with_test_db, client)
    r = client.post(
        "/api/schedules",
        headers={"X-Requested-With": "fetch"},
        json={
            "name": "bad",
            "ticker": "AAPL",
            "cron_expr": "not a cron",
            "preset": {"analysts": ["market"], "debate_rounds": 1},
        },
    )
    assert r.status_code == 422


def test_pause_resume_schedule(app_with_test_db, client):
    client = _login(app_with_test_db, client)
    r = client.post(
        "/api/schedules",
        headers={"X-Requested-With": "fetch"},
        json={
            "name": "S",
            "ticker": "AAPL",
            "cron_expr": "0 9 * * *",
            "preset": {"analysts": ["market"], "debate_rounds": 1},
        },
    )
    sid = r.json()["id"]

    r2 = client.patch(
        f"/api/schedules/{sid}",
        headers={"X-Requested-With": "fetch"},
        json={"active": False},
    )
    assert r2.status_code == 200
    assert r2.json()["active"] is False

    r3 = client.patch(
        f"/api/schedules/{sid}",
        headers={"X-Requested-With": "fetch"},
        json={"active": True},
    )
    assert r3.status_code == 200
    assert r3.json()["active"] is True


def test_delete_schedule(app_with_test_db, client):
    client = _login(app_with_test_db, client)
    r = client.post(
        "/api/schedules",
        headers={"X-Requested-With": "fetch"},
        json={
            "name": "Z",
            "ticker": "AAPL",
            "cron_expr": "0 9 * * *",
            "preset": {"analysts": ["market"], "debate_rounds": 1},
        },
    )
    sid = r.json()["id"]
    r2 = client.delete(
        f"/api/schedules/{sid}",
        headers={"X-Requested-With": "fetch"},
    )
    assert r2.status_code == 204


def test_run_now_creates_analysis(monkeypatch, app_with_test_db, client):
    monkeypatch.setenv("WEB_FAKE_RUNNER", "true")
    monkeypatch.setenv("WEB_FAKE_RUNNER_DELAY_SECONDS", "0")

    client = _login(app_with_test_db, client)
    r = client.post(
        "/api/schedules",
        headers={"X-Requested-With": "fetch"},
        json={
            "name": "X",
            "ticker": "AAPL",
            "cron_expr": "0 9 * * *",
            "preset": {"analysts": ["market"], "debate_rounds": 1},
        },
    )
    sid = r.json()["id"]
    r2 = client.post(
        f"/api/schedules/{sid}/run",
        headers={"X-Requested-With": "fetch"},
    )
    assert r2.status_code == 202, r2.text
    body = r2.json()
    assert "run_id" in body
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/web/test_schedules_api.py -v`
Expected: 404 (router 미등록).

- [ ] **Step 3: 구현**

`tradingagents_web/api/schedules.py`:

```python
"""Schedules CRUD + run-now API."""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as OrmSession

from tradingagents_web.auth import get_current_user, require_xhr
from tradingagents_web.db import get_db
from tradingagents_web.models import Schedule, User
from tradingagents_web.schemas.schedule import (
    ScheduleCreate,
    ScheduleItem,
    ScheduleListResponse,
    ScheduleUpdate,
)
from tradingagents_web.services import auto_runner
from tradingagents_web.services import scheduler as scheduler_module

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/schedules", tags=["schedules"])


def _try_register(s: Schedule) -> None:
    try:
        svc = scheduler_module.get_scheduler()
    except RuntimeError:
        return
    svc.register(s)


def _try_unregister(schedule_id: int) -> None:
    try:
        svc = scheduler_module.get_scheduler()
    except RuntimeError:
        return
    svc.unregister(schedule_id)


def _hydrate(s: Schedule) -> ScheduleItem:
    item = ScheduleItem.model_validate(s)
    try:
        svc = scheduler_module.get_scheduler()
        nxt = svc.next_run(s.id)
        if nxt is not None:
            item = item.model_copy(update={"next_run": nxt})
    except RuntimeError:
        pass
    return item


@router.get("", response_model=ScheduleListResponse)
def list_schedules(
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> ScheduleListResponse:
    rows = db.query(Schedule).order_by(Schedule.created_at.desc()).all()
    return ScheduleListResponse(items=[_hydrate(r) for r in rows])


@router.post(
    "",
    response_model=ScheduleItem,
    status_code=status.HTTP_201_CREATED,
)
def create_schedule(
    payload: ScheduleCreate,
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> ScheduleItem:
    s = Schedule(
        name=payload.name,
        ticker=payload.ticker,
        cron_expr=payload.cron_expr,
        preset=payload.preset.model_dump(),
        active=payload.active,
        source="user",
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    _try_register(s)
    return _hydrate(s)


@router.patch("/{schedule_id}", response_model=ScheduleItem)
def update_schedule(
    schedule_id: int,
    payload: ScheduleUpdate,
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> ScheduleItem:
    s = db.query(Schedule).get(schedule_id)
    if s is None:
        raise HTTPException(status_code=404, detail="schedule not found")
    if payload.name is not None:
        s.name = payload.name
    if payload.cron_expr is not None:
        s.cron_expr = payload.cron_expr
    if payload.preset is not None:
        s.preset = payload.preset.model_dump()
    if payload.active is not None:
        s.active = payload.active
    db.commit()
    db.refresh(s)
    if s.active:
        _try_register(s)
    else:
        _try_unregister(s.id)
    return _hydrate(s)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    schedule_id: int,
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> None:
    s = db.query(Schedule).get(schedule_id)
    if s is None:
        raise HTTPException(status_code=404, detail="schedule not found")
    _try_unregister(s.id)
    db.delete(s)
    db.commit()
    return None


@router.post("/{schedule_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def run_now(
    schedule_id: int,
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> dict[str, str]:
    s = db.query(Schedule).get(schedule_id)
    if s is None:
        raise HTTPException(status_code=404, detail="schedule not found")
    run_id = await auto_runner.trigger_run(schedule_id)
    if run_id is None:
        raise HTTPException(status_code=409, detail="schedule inactive")
    return {"run_id": run_id}
```

- [ ] **Step 4: main.py에 등록**

`tradingagents_web/main.py`의 `create_app`에 추가:

```python
    from tradingagents_web.api import schedules as schedules_api
    app.include_router(schedules_api.router)
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `uv run pytest tests/web/test_schedules_api.py -v`
Expected: 모두 pass.

- [ ] **Step 6: 커밋**

```bash
git add tradingagents_web/api/schedules.py tradingagents_web/main.py tests/web/test_schedules_api.py
git commit -m "feat(web): add schedules CRUD + run-now API"
```

---

## Task 9: Prices API

**Files:**
- Create: `tradingagents_web/api/prices.py`
- Create: `tests/web/test_prices_api.py`

- [ ] **Step 1: 테스트 작성**

`tests/web/test_prices_api.py`:

```python
"""API tests for /api/prices."""
import pytest

from tradingagents_web.auth import create_session
from tradingagents_web.config import Settings
from tradingagents_web.models import User
from tradingagents_web.services import prices as prices_svc
from tradingagents_web.schemas.price import PriceHistoryResponse, PricePoint
from datetime import date

_settings = Settings()


def _login(app_with_test_db, client):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        user = User(password_hash="x")
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_session(db, user.id)
    finally:
        db.close()
    client.cookies.set(_settings.session_cookie_name, token)
    return client


def test_get_price_history(monkeypatch, app_with_test_db, client):
    fake = PriceHistoryResponse(
        ticker="AAPL",
        points=[PricePoint(date=date(2026, 4, 22), close=181.5)],
        last_close=181.5,
    )
    monkeypatch.setattr(prices_svc, "get_price_history", lambda t, days=90: fake)
    client = _login(app_with_test_db, client)
    r = client.get("/api/prices/aapl/history?days=30")
    assert r.status_code == 200
    body = r.json()
    assert body["ticker"] == "AAPL"
    assert body["last_close"] == 181.5


def test_get_price_history_requires_auth(client):
    r = client.get("/api/prices/AAPL/history")
    assert r.status_code == 401
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/web/test_prices_api.py -v`
Expected: 404.

- [ ] **Step 3: 구현**

`tradingagents_web/api/prices.py`:

```python
"""Read-only API for ticker price history."""
from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from tradingagents_web.auth import get_current_user
from tradingagents_web.models import User
from tradingagents_web.schemas.price import PriceHistoryResponse
from tradingagents_web.services import prices as prices_svc

router = APIRouter(prefix="/api/prices", tags=["prices"])


@router.get("/{ticker}/history", response_model=PriceHistoryResponse)
async def history(
    ticker: str,
    _user: Annotated[User, Depends(get_current_user)],
    days: int = Query(default=90, ge=1, le=730),
) -> PriceHistoryResponse:
    return await asyncio.to_thread(prices_svc.get_price_history, ticker, days)
```

- [ ] **Step 4: main.py에 등록**

```python
    from tradingagents_web.api import prices as prices_api
    app.include_router(prices_api.router)
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `uv run pytest tests/web/test_prices_api.py -v`
Expected: 2 passed.

- [ ] **Step 6: 커밋**

```bash
git add tradingagents_web/api/prices.py tradingagents_web/main.py tests/web/test_prices_api.py
git commit -m "feat(web): add prices history API"
```

---

## Task 10: FastAPI lifespan에 SchedulerService 연결

**Files:**
- Modify: `tradingagents_web/main.py`

- [ ] **Step 1: lifespan 추가**

`tradingagents_web/main.py` 전체를 다음으로 교체:

```python
"""FastAPI application factory and entrypoint."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from tradingagents_web.api import auth as auth_api
from tradingagents_web.api import health
from tradingagents_web.api import holdings as holdings_api
from tradingagents_web.api import prices as prices_api
from tradingagents_web.api import runs as runs_api
from tradingagents_web.api import schedules as schedules_api
from tradingagents_web.config import Settings
from tradingagents_web.db import SessionLocal
from tradingagents_web.services import auto_runner
from tradingagents_web.services import scheduler as scheduler_module
from tradingagents_web.services.scheduler import SchedulerService


class SessionRefreshMiddleware(BaseHTTPMiddleware):
    """Slide the session cookie expiry on every successful response."""

    def __init__(self, app, settings: Settings) -> None:
        super().__init__(app)
        self._settings = settings

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        token = request.cookies.get(self._settings.session_cookie_name)
        if token and response.status_code < 400:
            response.set_cookie(
                key=self._settings.session_cookie_name,
                value=token,
                max_age=self._settings.session_max_age_seconds,
                httponly=True,
                secure=self._settings.cookie_secure,
                samesite="strict",
                path="/",
            )
        return response


def _build_lifespan(settings: Settings):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        svc = SchedulerService(
            tz=settings.schedule_tz,
            grace_seconds=settings.scheduler_grace_seconds,
        )
        svc.set_trigger_callback(auto_runner.trigger_run)
        scheduler_module.set_scheduler(svc)
        svc.start()
        db = SessionLocal()
        try:
            svc.bootstrap(db)
        finally:
            db.close()
        try:
            yield
        finally:
            svc.shutdown()
            scheduler_module.set_scheduler(None)

    return lifespan


def create_app() -> FastAPI:
    settings = Settings()
    app = FastAPI(
        title="TradingAgents Web",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=_build_lifespan(settings),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SessionRefreshMiddleware, settings=settings)
    app.include_router(health.router)
    app.include_router(auth_api.router)
    app.include_router(runs_api.router)
    app.include_router(holdings_api.router)
    app.include_router(schedules_api.router)
    app.include_router(prices_api.router)
    return app


app = create_app()
```

- [ ] **Step 2: 통합 회귀 검증**

`TestClient`는 lifespan을 자동 트리거하지 않으므로, 기존 `app_with_test_db` 픽스쳐는 영향 없음(scheduler 부재 시 holdings/schedules API가 안전 fallback). 다만 lifespan을 활성화하는 별도 테스트로 부팅 절차를 확인:

`tests/web/test_lifespan.py`:

```python
"""Sanity check: app lifespan starts/stops the scheduler cleanly."""
from fastapi.testclient import TestClient

from tradingagents_web.main import create_app
from tradingagents_web.services import scheduler as scheduler_module


def test_lifespan_starts_scheduler(monkeypatch):
    app = create_app()
    with TestClient(app) as client:
        # When the TestClient context is open, lifespan startup has finished.
        svc = scheduler_module.get_scheduler()
        assert svc.is_running()
        r = client.get("/api/health")
        assert r.status_code == 200
    # On exit, lifespan shutdown runs.
    import pytest
    with pytest.raises(RuntimeError):
        scheduler_module.get_scheduler()
```

- [ ] **Step 3: 모든 백엔드 테스트 회귀**

Run: `uv run pytest tests/web -v`
Expected: 모두 pass (이전 마일스톤 포함).

- [ ] **Step 4: 커밋**

```bash
git add tradingagents_web/main.py tests/web/test_lifespan.py
git commit -m "feat(web): wire SchedulerService into FastAPI lifespan"
```

---

## Task 11: 프런트 — `lib/holdings.ts`, `lib/schedules.ts`, `lib/prices.ts`

**Files:**
- Create: `web/lib/holdings.ts`
- Create: `web/lib/schedules.ts`
- Create: `web/lib/prices.ts`

- [ ] **Step 1: holdings.ts**

```typescript
import { api } from "./api";

export interface Holding {
  id: number;
  ticker: string;
  qty: number;
  avg_cost: number;
  monitor_enabled: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface HoldingListResponse {
  items: Holding[];
}

export interface HoldingCreatePayload {
  ticker: string;
  qty: number;
  avg_cost: number;
  notes?: string;
}

export interface HoldingUpdatePayload {
  qty?: number;
  avg_cost?: number;
  monitor_enabled?: boolean;
  notes?: string;
}

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export async function listHoldings(): Promise<HoldingListResponse> {
  return api(`${BASE}/api/holdings`);
}

export async function createHolding(p: HoldingCreatePayload): Promise<Holding> {
  return api(`${BASE}/api/holdings`, {
    method: "POST",
    body: JSON.stringify(p),
  });
}

export async function updateHolding(
  id: number,
  p: HoldingUpdatePayload,
): Promise<Holding> {
  return api(`${BASE}/api/holdings/${id}`, {
    method: "PATCH",
    body: JSON.stringify(p),
  });
}

export async function deleteHolding(id: number): Promise<void> {
  return api(`${BASE}/api/holdings/${id}`, { method: "DELETE" });
}
```

- [ ] **Step 2: schedules.ts**

```typescript
import { api } from "./api";

export interface SchedulePreset {
  analysts: string[];
  debate_rounds: number;
  llm_provider?: string | null;
  llm_deep_model?: string | null;
  llm_quick_model?: string | null;
}

export interface Schedule {
  id: number;
  name: string;
  ticker: string;
  cron_expr: string;
  preset: SchedulePreset;
  active: boolean;
  last_run: string | null;
  next_run: string | null;
  source: "user" | "holding";
  holding_id: number | null;
  created_at: string;
}

export interface ScheduleListResponse {
  items: Schedule[];
}

export interface ScheduleCreatePayload {
  name: string;
  ticker: string;
  cron_expr: string;
  preset: SchedulePreset;
  active?: boolean;
}

export interface ScheduleUpdatePayload {
  name?: string;
  cron_expr?: string;
  preset?: SchedulePreset;
  active?: boolean;
}

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export async function listSchedules(): Promise<ScheduleListResponse> {
  return api(`${BASE}/api/schedules`);
}

export async function createSchedule(p: ScheduleCreatePayload): Promise<Schedule> {
  return api(`${BASE}/api/schedules`, {
    method: "POST",
    body: JSON.stringify(p),
  });
}

export async function updateSchedule(
  id: number,
  p: ScheduleUpdatePayload,
): Promise<Schedule> {
  return api(`${BASE}/api/schedules/${id}`, {
    method: "PATCH",
    body: JSON.stringify(p),
  });
}

export async function deleteSchedule(id: number): Promise<void> {
  return api(`${BASE}/api/schedules/${id}`, { method: "DELETE" });
}

export async function runScheduleNow(id: number): Promise<{ run_id: string }> {
  return api(`${BASE}/api/schedules/${id}/run`, { method: "POST" });
}
```

- [ ] **Step 3: prices.ts**

```typescript
import { api } from "./api";

export interface PricePoint {
  date: string;
  close: number;
}

export interface PriceHistoryResponse {
  ticker: string;
  points: PricePoint[];
  last_close: number | null;
}

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export async function getPriceHistory(
  ticker: string,
  days: number = 90,
): Promise<PriceHistoryResponse> {
  return api(`${BASE}/api/prices/${encodeURIComponent(ticker)}/history?days=${days}`);
}
```

- [ ] **Step 4: 타입 체크**

Run: `cd web && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 5: 커밋**

```bash
git add web/lib/holdings.ts web/lib/schedules.ts web/lib/prices.ts
git commit -m "feat(web): add holdings/schedules/prices lib clients"
```

---

## Task 12: 프런트 — TanStack Query 훅

**Files:**
- Create: `web/hooks/use-holdings.ts`
- Create: `web/hooks/use-schedules.ts`
- Create: `web/hooks/use-price-history.ts`

- [ ] **Step 1: use-holdings.ts**

```typescript
"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Holding,
  HoldingCreatePayload,
  HoldingUpdatePayload,
  createHolding,
  deleteHolding,
  listHoldings,
  updateHolding,
} from "@/lib/holdings";

export function useHoldings() {
  return useQuery({
    queryKey: ["holdings"],
    queryFn: listHoldings,
  });
}

export function useCreateHolding() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: HoldingCreatePayload) => createHolding(p),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["holdings"] }),
  });
}

export function useUpdateHolding() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: HoldingUpdatePayload }) =>
      updateHolding(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["holdings"] });
      qc.invalidateQueries({ queryKey: ["schedules"] });
    },
  });
}

export function useDeleteHolding() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deleteHolding(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["holdings"] });
      qc.invalidateQueries({ queryKey: ["schedules"] });
    },
  });
}
```

- [ ] **Step 2: use-schedules.ts**

```typescript
"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Schedule,
  ScheduleCreatePayload,
  ScheduleUpdatePayload,
  createSchedule,
  deleteSchedule,
  listSchedules,
  runScheduleNow,
  updateSchedule,
} from "@/lib/schedules";

export function useSchedules() {
  return useQuery({
    queryKey: ["schedules"],
    queryFn: listSchedules,
  });
}

export function useCreateSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: ScheduleCreatePayload) => createSchedule(p),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["schedules"] }),
  });
}

export function useUpdateSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: ScheduleUpdatePayload }) =>
      updateSchedule(id, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["schedules"] }),
  });
}

export function useDeleteSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deleteSchedule(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["schedules"] }),
  });
}

export function useRunScheduleNow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => runScheduleNow(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["schedules"] });
      qc.invalidateQueries({ queryKey: ["runs"] });
    },
  });
}
```

- [ ] **Step 3: use-price-history.ts**

```typescript
"use client";
import { useQuery } from "@tanstack/react-query";
import { getPriceHistory } from "@/lib/prices";

export function usePriceHistory(ticker: string | undefined, days: number = 90) {
  return useQuery({
    queryKey: ["prices", ticker, days],
    queryFn: () => getPriceHistory(ticker!, days),
    enabled: !!ticker,
    staleTime: 60_000,
  });
}
```

- [ ] **Step 4: 타입 체크**

Run: `cd web && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 5: 커밋**

```bash
git add web/hooks/use-holdings.ts web/hooks/use-schedules.ts web/hooks/use-price-history.ts
git commit -m "feat(web): add TanStack Query hooks for holdings/schedules/prices"
```

---

## Task 13: 프런트 — 공유 컴포넌트 + Recharts 의존성

**Files:**
- Modify: `web/package.json`
- Create: `web/components/portfolio/holding-form.tsx`
- Create: `web/components/portfolio/holdings-table.tsx`
- Create: `web/components/portfolio/monitor-toggle.tsx`
- Create: `web/components/portfolio/pnl-cell.tsx`
- Create: `web/components/portfolio/price-chart.tsx`
- Create: `web/components/schedules/cron-helper.tsx`
- Create: `web/components/schedules/schedule-form.tsx`
- Create: `web/components/schedules/schedules-table.tsx`
- Create: `web/components/dashboard/metric-card.tsx`
- Create: `web/components/dashboard/portfolio-signals.tsx`
- Create: `web/components/ui/switch.tsx` (shadcn)

- [ ] **Step 1: 의존성 추가**

`web/package.json`의 `dependencies`에 추가:

```json
"recharts": "^2.13.0",
"@radix-ui/react-switch": "^1.1.0"
```

Run:

```bash
cd web && npm install
```

- [ ] **Step 2: shadcn switch 컴포넌트**

`web/components/ui/switch.tsx`:

```tsx
"use client";
import * as React from "react";
import * as SwitchPrimitives from "@radix-ui/react-switch";
import { cn } from "@/lib/utils";

const Switch = React.forwardRef<
  React.ElementRef<typeof SwitchPrimitives.Root>,
  React.ComponentPropsWithoutRef<typeof SwitchPrimitives.Root>
>(({ className, ...props }, ref) => (
  <SwitchPrimitives.Root
    className={cn(
      "peer inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border border-border-2 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-accent data-[state=unchecked]:bg-bg-2",
      className,
    )}
    {...props}
    ref={ref}
  >
    <SwitchPrimitives.Thumb
      className={cn(
        "pointer-events-none block h-4 w-4 rounded-full bg-text-1 shadow-lg ring-0 transition-transform data-[state=checked]:translate-x-4 data-[state=unchecked]:translate-x-0.5",
      )}
    />
  </SwitchPrimitives.Root>
));
Switch.displayName = SwitchPrimitives.Root.displayName;

export { Switch };
```

- [ ] **Step 3: holding-form.tsx**

```tsx
"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useCreateHolding } from "@/hooks/use-holdings";

export function HoldingForm({ onCreated }: { onCreated?: () => void }) {
  const [ticker, setTicker] = useState("");
  const [qty, setQty] = useState("");
  const [avg, setAvg] = useState("");
  const [notes, setNotes] = useState("");
  const m = useCreateHolding();

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    m.mutate(
      {
        ticker,
        qty: Number(qty),
        avg_cost: Number(avg),
        notes: notes || undefined,
      },
      {
        onSuccess: () => {
          setTicker("");
          setQty("");
          setAvg("");
          setNotes("");
          onCreated?.();
        },
      },
    );
  };

  return (
    <form onSubmit={submit} className="grid grid-cols-1 md:grid-cols-5 gap-3 items-end">
      <div>
        <Label htmlFor="ticker">Ticker</Label>
        <Input
          id="ticker"
          required
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          placeholder="AAPL"
        />
      </div>
      <div>
        <Label htmlFor="qty">Quantity</Label>
        <Input
          id="qty"
          type="number"
          step="any"
          min="0"
          required
          value={qty}
          onChange={(e) => setQty(e.target.value)}
        />
      </div>
      <div>
        <Label htmlFor="avg">Avg cost</Label>
        <Input
          id="avg"
          type="number"
          step="any"
          min="0"
          required
          value={avg}
          onChange={(e) => setAvg(e.target.value)}
        />
      </div>
      <div className="md:col-span-1">
        <Label htmlFor="notes">Notes</Label>
        <Input
          id="notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="optional"
        />
      </div>
      <Button type="submit" disabled={m.isPending}>
        {m.isPending ? "Adding…" : "Add"}
      </Button>
      {m.error ? <p className="text-xs text-neg col-span-full">{(m.error as Error).message}</p> : null}
    </form>
  );
}
```

- [ ] **Step 4: monitor-toggle.tsx**

```tsx
"use client";
import { Switch } from "@/components/ui/switch";
import { useUpdateHolding } from "@/hooks/use-holdings";

export function MonitorToggle({
  holdingId,
  enabled,
}: {
  holdingId: number;
  enabled: boolean;
}) {
  const m = useUpdateHolding();
  return (
    <Switch
      checked={enabled}
      disabled={m.isPending}
      onCheckedChange={(v) =>
        m.mutate({ id: holdingId, payload: { monitor_enabled: v } })
      }
    />
  );
}
```

- [ ] **Step 5: pnl-cell.tsx**

```tsx
import { cn } from "@/lib/utils";

export function PnLCell({
  qty,
  avgCost,
  lastPrice,
}: {
  qty: number;
  avgCost: number;
  lastPrice: number | null;
}) {
  if (lastPrice == null) return <span className="text-text-3 font-mono text-xs">—</span>;
  const cost = qty * avgCost;
  const value = qty * lastPrice;
  const pnl = value - cost;
  const pct = cost > 0 ? (pnl / cost) * 100 : 0;
  const cls = pnl >= 0 ? "text-pos" : "text-neg";
  return (
    <span className={cn("font-mono text-xs tabular-nums", cls)}>
      {pnl >= 0 ? "+" : ""}
      {pnl.toFixed(2)} ({pct >= 0 ? "+" : ""}
      {pct.toFixed(1)}%)
    </span>
  );
}
```

- [ ] **Step 6: holdings-table.tsx**

```tsx
"use client";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Holding } from "@/lib/holdings";
import { useDeleteHolding } from "@/hooks/use-holdings";
import { MonitorToggle } from "./monitor-toggle";
import { PnLCell } from "./pnl-cell";

export function HoldingsTable({
  rows,
  prices,
}: {
  rows: Holding[];
  prices: Record<string, number | null>;
}) {
  const del = useDeleteHolding();
  if (rows.length === 0) {
    return (
      <p className="text-sm text-text-3 py-8 text-center">
        No holdings yet — add a ticker above.
      </p>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-[10px] uppercase tracking-wider text-text-3 border-b border-border-1">
            <th className="text-left py-2">Ticker</th>
            <th className="text-right">Qty</th>
            <th className="text-right">Avg Cost</th>
            <th className="text-right">Last</th>
            <th className="text-right">P&L</th>
            <th className="text-center">Monitor</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((h) => {
            const last = prices[h.ticker] ?? null;
            return (
              <tr key={h.id} className="border-b border-border-1 hover:bg-bg-2">
                <td className="py-2 font-mono">
                  <Link className="hover:underline" href={`/portfolio/${h.ticker}`}>
                    {h.ticker}
                  </Link>
                </td>
                <td className="text-right font-mono tabular-nums">{h.qty}</td>
                <td className="text-right font-mono tabular-nums">
                  {h.avg_cost.toFixed(2)}
                </td>
                <td className="text-right font-mono tabular-nums">
                  {last == null ? "—" : last.toFixed(2)}
                </td>
                <td className="text-right">
                  <PnLCell qty={h.qty} avgCost={h.avg_cost} lastPrice={last} />
                </td>
                <td className="text-center">
                  <MonitorToggle holdingId={h.id} enabled={h.monitor_enabled} />
                </td>
                <td className="text-right">
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={del.isPending}
                    onClick={() => del.mutate(h.id)}
                  >
                    Remove
                  </Button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 7: price-chart.tsx**

```tsx
"use client";
import {
  Line,
  LineChart,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { PricePoint } from "@/lib/prices";

export interface SignalMarker {
  date: string;
  decision: "BUY" | "SELL" | "HOLD" | "OVERWEIGHT" | "UNDERWEIGHT";
  close: number;
}

const decisionColor: Record<string, string> = {
  BUY: "var(--pos)",
  OVERWEIGHT: "var(--pos)",
  SELL: "var(--neg)",
  UNDERWEIGHT: "var(--neg)",
  HOLD: "var(--warn)",
};

export function PriceChart({
  points,
  signals = [],
}: {
  points: PricePoint[];
  signals?: SignalMarker[];
}) {
  if (points.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-text-3 text-sm">
        No price data
      </div>
    );
  }
  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <XAxis
            dataKey="date"
            stroke="#6b6b74"
            fontSize={10}
            tick={{ fill: "#6b6b74" }}
          />
          <YAxis
            stroke="#6b6b74"
            fontSize={10}
            tick={{ fill: "#6b6b74" }}
            domain={["auto", "auto"]}
          />
          <Tooltip
            contentStyle={{
              background: "#111114",
              border: "1px solid #25252b",
              fontSize: 12,
            }}
            labelStyle={{ color: "#a0a0a8" }}
          />
          <Line
            type="monotone"
            dataKey="close"
            stroke="#4f8cff"
            strokeWidth={1.5}
            dot={false}
          />
          {signals.map((s, i) => (
            <ReferenceDot
              key={`${s.date}-${i}`}
              x={s.date}
              y={s.close}
              r={4}
              fill={decisionColor[s.decision] ?? "#a0a0a8"}
              stroke="none"
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 8: cron-helper.tsx**

```tsx
"use client";

const PRESETS: { label: string; cron: string; hint: string }[] = [
  { label: "Daily 09:30 ET", cron: "30 9 * * *", hint: "morning" },
  { label: "Daily 16:30 ET", cron: "30 16 * * *", hint: "after close" },
  { label: "Weekdays 16:30 ET", cron: "30 16 * * 1-5", hint: "Mon–Fri" },
  { label: "Mon 09:00 ET", cron: "0 9 * * 1", hint: "weekly" },
];

export function CronHelper({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1">
      {PRESETS.map((p) => (
        <button
          type="button"
          key={p.cron}
          onClick={() => onChange(p.cron)}
          className={`text-[10px] px-2 py-1 rounded-md border ${
            value === p.cron
              ? "bg-accent/20 border-accent text-text-1"
              : "bg-bg-2 border-border-1 text-text-2 hover:text-text-1"
          }`}
        >
          {p.label}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 9: schedule-form.tsx**

```tsx
"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { useCreateSchedule } from "@/hooks/use-schedules";
import { CronHelper } from "./cron-helper";

const ANALYSTS = ["market", "social", "news", "fundamentals"] as const;

export function ScheduleForm() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [tickers, setTickers] = useState("");
  const [cron, setCron] = useState("30 16 * * 1-5");
  const [rounds, setRounds] = useState(1);
  const [analysts, setAnalysts] = useState<string[]>([...ANALYSTS]);
  const m = useCreateSchedule();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const tickerList = tickers
      .split(/[,\s]+/)
      .map((t) => t.trim().toUpperCase())
      .filter(Boolean);
    for (const t of tickerList) {
      await m.mutateAsync({
        name: tickerList.length === 1 ? name : `${name} (${t})`,
        ticker: t,
        cron_expr: cron,
        preset: { analysts, debate_rounds: rounds },
      });
    }
    router.push("/schedules");
  };

  const toggleAnalyst = (a: string) => {
    setAnalysts((cur) =>
      cur.includes(a) ? cur.filter((x) => x !== a) : [...cur, a],
    );
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-4 max-w-xl">
      <div>
        <Label htmlFor="name">Name</Label>
        <Input
          id="name"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Semi-cap weekly"
        />
      </div>
      <div>
        <Label htmlFor="tickers">Tickers (comma or space separated)</Label>
        <Input
          id="tickers"
          required
          value={tickers}
          onChange={(e) => setTickers(e.target.value)}
          placeholder="AAPL, NVDA, AMD"
        />
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="cron">Cron</Label>
        <Input
          id="cron"
          required
          value={cron}
          onChange={(e) => setCron(e.target.value)}
          className="font-mono"
        />
        <CronHelper value={cron} onChange={setCron} />
      </div>
      <div>
        <Label>Analysts</Label>
        <div className="flex gap-3 mt-1">
          {ANALYSTS.map((a) => (
            <label key={a} className="flex items-center gap-1 text-xs">
              <Checkbox
                checked={analysts.includes(a)}
                onCheckedChange={() => toggleAnalyst(a)}
              />
              {a}
            </label>
          ))}
        </div>
      </div>
      <div className="w-32">
        <Label htmlFor="rounds">Debate rounds</Label>
        <Input
          id="rounds"
          type="number"
          min="1"
          max="5"
          value={rounds}
          onChange={(e) => setRounds(Number(e.target.value))}
        />
      </div>
      <Button type="submit" disabled={m.isPending}>
        {m.isPending ? "Creating…" : "Create schedule(s)"}
      </Button>
      {m.error ? <p className="text-xs text-neg">{(m.error as Error).message}</p> : null}
    </form>
  );
}
```

- [ ] **Step 10: schedules-table.tsx**

```tsx
"use client";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
  useDeleteSchedule,
  useRunScheduleNow,
  useUpdateSchedule,
} from "@/hooks/use-schedules";
import { Schedule } from "@/lib/schedules";

function fmt(d: string | null) {
  return d ? new Date(d).toLocaleString() : "—";
}

export function SchedulesTable({ rows }: { rows: Schedule[] }) {
  const upd = useUpdateSchedule();
  const del = useDeleteSchedule();
  const run = useRunScheduleNow();
  if (rows.length === 0)
    return (
      <p className="text-sm text-text-3 py-8 text-center">No schedules yet.</p>
    );
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-[10px] uppercase tracking-wider text-text-3 border-b border-border-1">
            <th className="text-left py-2">Name</th>
            <th>Ticker</th>
            <th>Cron</th>
            <th>Source</th>
            <th>Next run</th>
            <th>Last run</th>
            <th>Active</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => (
            <tr key={s.id} className="border-b border-border-1 hover:bg-bg-2">
              <td className="py-2">{s.name}</td>
              <td className="font-mono text-xs">{s.ticker}</td>
              <td className="font-mono text-xs">{s.cron_expr}</td>
              <td className="text-xs text-text-3">{s.source}</td>
              <td className="text-xs">{fmt(s.next_run)}</td>
              <td className="text-xs">{fmt(s.last_run)}</td>
              <td className="text-center">
                <Switch
                  checked={s.active}
                  disabled={upd.isPending}
                  onCheckedChange={(v) =>
                    upd.mutate({ id: s.id, payload: { active: v } })
                  }
                />
              </td>
              <td className="text-right space-x-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={run.isPending}
                  onClick={() => run.mutate(s.id)}
                >
                  Run now
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={del.isPending || s.source === "holding"}
                  onClick={() => del.mutate(s.id)}
                >
                  Delete
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 11: dashboard 컴포넌트**

`web/components/dashboard/metric-card.tsx`:

```tsx
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function MetricCard({
  label,
  value,
  delta,
  tone = "neutral",
}: {
  label: string;
  value: string;
  delta?: string;
  tone?: "neutral" | "pos" | "neg";
}) {
  const toneCls =
    tone === "pos" ? "text-pos" : tone === "neg" ? "text-neg" : "text-text-1";
  return (
    <Card>
      <CardContent className="py-4">
        <div className="text-[10px] uppercase tracking-widest text-text-3">
          {label}
        </div>
        <div className={cn("font-mono text-xl tabular-nums mt-1", toneCls)}>
          {value}
        </div>
        {delta && (
          <div className="text-xs text-text-3 mt-1 font-mono">{delta}</div>
        )}
      </CardContent>
    </Card>
  );
}
```

`web/components/dashboard/portfolio-signals.tsx`:

```tsx
"use client";
import { Holding } from "@/lib/holdings";
import { RunListItem } from "@/lib/runs";
import { SignalBadge } from "@/components/shared/signal-badge";
import Link from "next/link";

export function PortfolioSignals({
  holdings,
  latestByTicker,
}: {
  holdings: Holding[];
  latestByTicker: Record<string, RunListItem | undefined>;
}) {
  if (holdings.length === 0)
    return (
      <p className="text-sm text-text-3">No holdings — add one in Portfolio.</p>
    );
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-[10px] uppercase tracking-wider text-text-3 border-b border-border-1">
            <th className="text-left py-2">Ticker</th>
            <th>Latest decision</th>
            <th>Confidence</th>
            <th>When</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((h) => {
            const r = latestByTicker[h.ticker];
            return (
              <tr key={h.id} className="border-b border-border-1 hover:bg-bg-2">
                <td className="py-2 font-mono">
                  <Link className="hover:underline" href={`/portfolio/${h.ticker}`}>
                    {h.ticker}
                  </Link>
                </td>
                <td>
                  {r?.decision ? <SignalBadge decision={r.decision} /> : "—"}
                </td>
                <td className="font-mono tabular-nums">
                  {r?.confidence != null ? r.confidence.toFixed(2) : "—"}
                </td>
                <td className="text-xs text-text-3">
                  {r ? new Date(r.created_at).toLocaleString() : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 12: 타입 체크**

Run: `cd web && npx tsc --noEmit`
Expected: No errors. (If `Checkbox` is not exported, add a shadcn checkbox via the M2 task or create one analogously to `switch.tsx`.)

- [ ] **Step 13: 커밋**

```bash
git add web/package.json web/package-lock.json \
    web/components/portfolio/ web/components/schedules/ web/components/dashboard/ web/components/ui/switch.tsx
git commit -m "feat(web): add portfolio/schedules/dashboard components + recharts"
```

---

## Task 14: 프런트 — `/portfolio` 페이지

**Files:**
- Create: `web/app/(workspace)/portfolio/page.tsx`

- [ ] **Step 1: 구현**

```tsx
"use client";
import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useHoldings } from "@/hooks/use-holdings";
import { HoldingForm } from "@/components/portfolio/holding-form";
import { HoldingsTable } from "@/components/portfolio/holdings-table";
import { getPriceHistory } from "@/lib/prices";

export default function PortfolioPage() {
  const { data, isLoading, error } = useHoldings();
  const [prices, setPrices] = useState<Record<string, number | null>>({});

  useEffect(() => {
    if (!data?.items) return;
    let cancelled = false;
    (async () => {
      const result: Record<string, number | null> = {};
      await Promise.all(
        data.items.map(async (h) => {
          try {
            const r = await getPriceHistory(h.ticker, 5);
            result[h.ticker] = r.last_close;
          } catch {
            result[h.ticker] = null;
          }
        }),
      );
      if (!cancelled) setPrices(result);
    })();
    return () => {
      cancelled = true;
    };
  }, [data?.items]);

  return (
    <div className="px-4 md:px-6 py-6 md:py-8 max-w-screen-xl mx-auto">
      <h1 className="text-xl font-bold text-text-1 mb-1">Portfolio</h1>
      <p className="text-xs text-text-3 mb-6">
        Track holdings and toggle daily auto-monitoring.
      </p>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Add holding</CardTitle>
        </CardHeader>
        <CardContent>
          <HoldingForm />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Holdings</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-sm text-text-3">Loading…</p>
          ) : error ? (
            <p className="text-sm text-neg">{(error as Error).message}</p>
          ) : (
            <HoldingsTable rows={data?.items ?? []} prices={prices} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: 빌드 확인**

Run: `cd web && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 3: 수동 검증**

Run dev (별도 터미널):

```bash
WEB_FAKE_RUNNER=true uv run uvicorn tradingagents_web.main:app --port 8000 &
cd web && npm run dev
```

브라우저에서 `http://localhost:3000/portfolio`, 로그인 후 holding 추가 → 표에 노출 → monitor 토글 → DB에 schedule 행 생기는지 (`sqlite3 tradingagents_web.db 'select * from schedules'`).

- [ ] **Step 4: 커밋**

```bash
git add web/app/\(workspace\)/portfolio/page.tsx
git commit -m "feat(web): add /portfolio list + add page"
```

---

## Task 15: 프런트 — `/portfolio/[ticker]` 상세 페이지

**Files:**
- Create: `web/app/(workspace)/portfolio/[ticker]/page.tsx`

- [ ] **Step 1: 구현**

```tsx
"use client";
import Link from "next/link";
import { useMemo } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useHoldings } from "@/hooks/use-holdings";
import { useRunList } from "@/hooks/use-runs";
import { usePriceHistory } from "@/hooks/use-price-history";
import { PriceChart, SignalMarker } from "@/components/portfolio/price-chart";
import { SignalBadge } from "@/components/shared/signal-badge";

export default function PortfolioDetail() {
  const params = useParams<{ ticker: string }>();
  const ticker = params.ticker.toUpperCase();
  const { data: holdings } = useHoldings();
  const { data: history } = useRunList({ ticker, page_size: 50 });
  const { data: price, isLoading: priceLoading } = usePriceHistory(ticker, 90);

  const holding = holdings?.items.find((h) => h.ticker === ticker);

  const signals: SignalMarker[] = useMemo(() => {
    if (!history?.items || !price?.points) return [];
    const closeByDate = new Map(price.points.map((p) => [p.date, p.close]));
    const out: SignalMarker[] = [];
    for (const r of history.items) {
      if (!r.decision) continue;
      const c = closeByDate.get(r.analysis_date);
      if (c == null) continue;
      out.push({ date: r.analysis_date, decision: r.decision, close: c });
    }
    return out;
  }, [history?.items, price?.points]);

  const last = price?.last_close ?? null;
  const cost = holding ? holding.qty * holding.avg_cost : 0;
  const value = holding && last != null ? holding.qty * last : null;
  const pnl = value != null ? value - cost : null;

  return (
    <div className="px-4 md:px-6 py-6 md:py-8 max-w-screen-xl mx-auto space-y-6">
      <div className="flex items-baseline gap-3">
        <h1 className="text-2xl font-bold font-mono">{ticker}</h1>
        <Link href="/portfolio" className="text-xs text-text-3 hover:underline">
          ← back to portfolio
        </Link>
      </div>

      {holding ? (
        <Card>
          <CardContent className="py-4 grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <div className="text-[10px] uppercase tracking-widest text-text-3">
                Quantity
              </div>
              <div className="font-mono tabular-nums">{holding.qty}</div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-widest text-text-3">
                Avg cost
              </div>
              <div className="font-mono tabular-nums">{holding.avg_cost.toFixed(2)}</div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-widest text-text-3">
                Last
              </div>
              <div className="font-mono tabular-nums">
                {last != null ? last.toFixed(2) : "—"}
              </div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-widest text-text-3">
                P&L
              </div>
              <div
                className={`font-mono tabular-nums ${
                  pnl == null ? "" : pnl >= 0 ? "text-pos" : "text-neg"
                }`}
              >
                {pnl == null ? "—" : `${pnl >= 0 ? "+" : ""}${pnl.toFixed(2)}`}
              </div>
            </div>
          </CardContent>
        </Card>
      ) : (
        <p className="text-sm text-text-3">
          Not in portfolio. <Link className="underline" href="/portfolio">Add it</Link>.
        </p>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Price (90d)</CardTitle>
        </CardHeader>
        <CardContent>
          {priceLoading ? (
            <p className="text-sm text-text-3">Loading prices…</p>
          ) : (
            <PriceChart points={price?.points ?? []} signals={signals} />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Analysis history</CardTitle>
        </CardHeader>
        <CardContent>
          {history?.items.length === 0 ? (
            <p className="text-sm text-text-3">No analyses yet.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {history?.items.map((r) => (
                <li
                  key={r.run_id}
                  className="flex items-center justify-between border border-border-1 rounded-md px-3 py-2"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-text-3 font-mono">
                      {r.analysis_date}
                    </span>
                    {r.decision ? (
                      <SignalBadge decision={r.decision} />
                    ) : (
                      <span className="text-xs text-text-3">{r.status}</span>
                    )}
                    {r.confidence != null && (
                      <span className="text-xs text-text-3 font-mono">
                        conf {r.confidence.toFixed(2)}
                      </span>
                    )}
                  </div>
                  <Link
                    href={`/history/${r.run_id}`}
                    className="text-xs text-accent hover:underline"
                  >
                    Open →
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: 타입 체크 + 커밋**

Run: `cd web && npx tsc --noEmit`

```bash
git add web/app/\(workspace\)/portfolio/\[ticker\]/page.tsx
git commit -m "feat(web): add /portfolio/[ticker] detail with price chart + signals"
```

---

## Task 16: 프런트 — `/schedules` 페이지

**Files:**
- Create: `web/app/(workspace)/schedules/page.tsx`

- [ ] **Step 1: 구현**

```tsx
"use client";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useSchedules } from "@/hooks/use-schedules";
import { SchedulesTable } from "@/components/schedules/schedules-table";

export default function SchedulesPage() {
  const { data, isLoading, error } = useSchedules();
  return (
    <div className="px-4 md:px-6 py-6 md:py-8 max-w-screen-xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-text-1 mb-1">Schedules</h1>
          <p className="text-xs text-text-3">
            Cron-driven auto analyses. Holdings with monitor on appear here too.
          </p>
        </div>
        <Link href="/schedules/new">
          <Button>+ New schedule</Button>
        </Link>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All schedules</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-sm text-text-3">Loading…</p>
          ) : error ? (
            <p className="text-sm text-neg">{(error as Error).message}</p>
          ) : (
            <SchedulesTable rows={data?.items ?? []} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: 타입 체크 + 커밋**

Run: `cd web && npx tsc --noEmit`

```bash
git add web/app/\(workspace\)/schedules/page.tsx
git commit -m "feat(web): add /schedules list page"
```

---

## Task 17: 프런트 — `/schedules/new` 페이지

**Files:**
- Create: `web/app/(workspace)/schedules/new/page.tsx`

- [ ] **Step 1: 구현**

```tsx
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScheduleForm } from "@/components/schedules/schedule-form";

export default function NewSchedulePage() {
  return (
    <div className="px-4 md:px-6 py-6 md:py-8 max-w-screen-xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-text-1 mb-1">New schedule</h1>
        <p className="text-xs text-text-3">
          Pick tickers, a cron expression, and analysis preset.{" "}
          <Link className="underline" href="/schedules">Back to list</Link>
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Configuration</CardTitle>
        </CardHeader>
        <CardContent>
          <ScheduleForm />
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: 타입 체크 + 커밋**

Run: `cd web && npx tsc --noEmit`

```bash
git add web/app/\(workspace\)/schedules/new/page.tsx
git commit -m "feat(web): add /schedules/new creation page"
```

---

## Task 18: Dashboard `/` 갱신 (메트릭 카드 + 보유 시그널 테이블)

**Files:**
- Modify: `web/app/(workspace)/page.tsx`

- [ ] **Step 1: 구현**

`web/app/(workspace)/page.tsx`를 다음으로 교체:

```tsx
"use client";
import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { MetricCard } from "@/components/dashboard/metric-card";
import { PortfolioSignals } from "@/components/dashboard/portfolio-signals";
import { useHoldings } from "@/hooks/use-holdings";
import { useRunList } from "@/hooks/use-runs";
import { useSchedules } from "@/hooks/use-schedules";
import { getPriceHistory } from "@/lib/prices";
import { RunListItem } from "@/lib/runs";

export default function DashboardPage() {
  const { data: holdings } = useHoldings();
  const { data: schedules } = useSchedules();
  const { data: runs } = useRunList({ page_size: 100 });
  const [prices, setPrices] = useState<Record<string, number | null>>({});

  useEffect(() => {
    if (!holdings?.items) return;
    let cancelled = false;
    (async () => {
      const out: Record<string, number | null> = {};
      await Promise.all(
        holdings.items.map(async (h) => {
          try {
            const r = await getPriceHistory(h.ticker, 5);
            out[h.ticker] = r.last_close;
          } catch {
            out[h.ticker] = null;
          }
        }),
      );
      if (!cancelled) setPrices(out);
    })();
    return () => {
      cancelled = true;
    };
  }, [holdings?.items]);

  const totals = useMemo(() => {
    let value = 0;
    let cost = 0;
    let priced = 0;
    for (const h of holdings?.items ?? []) {
      cost += h.qty * h.avg_cost;
      const last = prices[h.ticker];
      if (last != null) {
        value += h.qty * last;
        priced += 1;
      }
    }
    const positions = holdings?.items.length ?? 0;
    const pnl = priced === positions && positions > 0 ? value - cost : null;
    return { value: priced === positions && positions > 0 ? value : null, cost, pnl, positions };
  }, [holdings?.items, prices]);

  const latestByTicker = useMemo(() => {
    const out: Record<string, RunListItem | undefined> = {};
    for (const r of runs?.items ?? []) {
      if (!out[r.ticker]) out[r.ticker] = r;
    }
    return out;
  }, [runs?.items]);

  const runningRuns = (runs?.items ?? []).filter((r) => r.status === "running");

  const fmtMoney = (n: number | null) =>
    n == null ? "—" : n.toLocaleString(undefined, { maximumFractionDigits: 2 });

  return (
    <div className="px-4 md:px-6 py-6 md:py-8 max-w-screen-xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-bold text-text-1 mb-1">Dashboard</h1>
        <p className="text-xs text-text-3">Personal workbench</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <MetricCard
          label="Portfolio value"
          value={fmtMoney(totals.value)}
          delta={`cost basis ${fmtMoney(totals.cost)}`}
        />
        <MetricCard
          label="Unrealized P&L"
          value={totals.pnl == null ? "—" : `${totals.pnl >= 0 ? "+" : ""}${totals.pnl.toFixed(2)}`}
          tone={totals.pnl == null ? "neutral" : totals.pnl >= 0 ? "pos" : "neg"}
        />
        <MetricCard
          label="Positions / Schedules"
          value={`${totals.positions} / ${schedules?.items.length ?? 0}`}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Holdings signals</CardTitle>
        </CardHeader>
        <CardContent>
          <PortfolioSignals
            holdings={holdings?.items ?? []}
            latestByTicker={latestByTicker}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Running</CardTitle>
        </CardHeader>
        <CardContent>
          {runningRuns.length === 0 ? (
            <p className="text-sm text-text-3">Nothing running.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {runningRuns.map((r) => (
                <li key={r.run_id} className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <span className="font-mono">{r.ticker}</span>
                    <span className="text-text-3 text-xs">{r.analysis_date}</span>
                  </div>
                  <Link href={`/run/${r.run_id}`} className="text-accent text-xs">
                    Watch →
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: 타입 체크 + 커밋**

Run: `cd web && npx tsc --noEmit`

```bash
git add web/app/\(workspace\)/page.tsx
git commit -m "feat(web): rebuild dashboard with metrics + holdings signals"
```

---

## Task 19: M3 happy-path 통합 테스트

**Goal:** login → holding 추가 → monitor ON → schedule 자동 생성 → schedule run-now → analysis 행 + SSE 이벤트 흐름 검증.

**Files:**
- Create: `tests/web/test_integration_m3.py`

- [ ] **Step 1: 테스트 작성**

```python
"""End-to-end M3 happy path: holdings/schedules/auto-run wiring."""
import time

import pytest

from tradingagents_web.auth import create_session
from tradingagents_web.config import Settings
from tradingagents_web.models import Analysis, Holding, Schedule, User
from tradingagents_web.services.event_bus import reset_event_bus

_settings = Settings()


@pytest.fixture(autouse=True)
def _reset_bus():
    reset_event_bus()
    yield
    reset_event_bus()


def _login(app_with_test_db, client):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        user = User(password_hash="x")
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_session(db, user.id)
    finally:
        db.close()
    client.cookies.set(_settings.session_cookie_name, token)
    return client


def test_m3_happy_path(monkeypatch, app_with_test_db, client):
    monkeypatch.setenv("WEB_FAKE_RUNNER", "true")
    monkeypatch.setenv("WEB_FAKE_RUNNER_DELAY_SECONDS", "0")

    client = _login(app_with_test_db, client)
    _, TestSessionLocal = app_with_test_db

    # 1. Add holding
    r = client.post(
        "/api/holdings",
        headers={"X-Requested-With": "fetch"},
        json={"ticker": "AAPL", "qty": 5, "avg_cost": 150},
    )
    assert r.status_code == 201
    hid = r.json()["id"]

    # 2. Toggle monitor → schedule auto-created
    r = client.patch(
        f"/api/holdings/{hid}",
        headers={"X-Requested-With": "fetch"},
        json={"monitor_enabled": True},
    )
    assert r.status_code == 200

    db = TestSessionLocal()
    try:
        sched = db.query(Schedule).filter_by(holding_id=hid, source="holding").one()
        sid = sched.id
    finally:
        db.close()

    # 3. Trigger run-now via API
    r = client.post(
        f"/api/schedules/{sid}/run",
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 202, r.text
    run_id = r.json()["run_id"]

    # 4. Wait for fake runner to finish (<= ~2s)
    deadline = time.time() + 5
    while time.time() < deadline:
        r2 = client.get(f"/api/runs/{run_id}")
        if r2.status_code == 200 and r2.json()["status"] == "completed":
            break
        time.sleep(0.05)
    assert r2.json()["status"] == "completed"
    assert r2.json()["schedule_id"] == sid

    # 5. Listing schedules + holdings reflects state
    db = TestSessionLocal()
    try:
        analyses = db.query(Analysis).filter_by(schedule_id=sid).all()
        assert len(analyses) == 1
        sched = db.query(Schedule).get(sid)
        assert sched.last_run is not None
    finally:
        db.close()

    # 6. Toggle monitor OFF → schedule removed
    r = client.patch(
        f"/api/holdings/{hid}",
        headers={"X-Requested-With": "fetch"},
        json={"monitor_enabled": False},
    )
    assert r.status_code == 200
    db = TestSessionLocal()
    try:
        rows = db.query(Schedule).filter_by(holding_id=hid).all()
        assert rows == []
    finally:
        db.close()
```

- [ ] **Step 2: 통과 확인**

Run: `uv run pytest tests/web/test_integration_m3.py -v`
Expected: 1 passed.

- [ ] **Step 3: 회귀 — 모든 테스트**

Run: `uv run pytest tests/web -v`
Expected: 모두 pass.

- [ ] **Step 4: 커밋**

```bash
git add tests/web/test_integration_m3.py
git commit -m "test(web): M3 holdings + schedules happy-path integration test"
```

---

## Task 20: DEV.md 업데이트 + 최종 수동 검증

**Files:**
- Modify: `DEV.md`

- [ ] **Step 1: DEV.md에 M3 섹션 추가**

`DEV.md` 끝에 추가:

```markdown
## M3 — Portfolio + Schedules

새 의존성: `apscheduler`, `croniter`. 기존 `uv sync` 후 사용 가능.

### 새 환경변수

| 이름 | 기본값 | 설명 |
|---|---|---|
| `WEB_SCHEDULE_TZ` | `America/New_York` | APScheduler 타임존 |
| `WEB_SCHEDULER_GRACE_SECONDS` | `60` | misfire grace 시간 |

### 사용 흐름

1. `/portfolio`에서 보유 종목 추가.
2. monitor 스위치 ON → 평일 16:30 ET 자동 분석 스케줄이 생성됨 (`/schedules`에서 확인).
3. `/schedules/new`에서 사용자 정의 cron + 다중 티커 등록 가능.
4. `Run now` 버튼으로 즉시 트리거 → `/history`에서 결과 확인.
5. `/portfolio/<TICKER>`에서 가격 차트 + 분석 시그널 마커 확인.

### 주의

- 스케줄러는 메모리(`MemoryJobStore`) 기반이므로 서버 재시작 시 `schedules` 테이블의 `active=True` 항목이 lifespan에서 다시 등록된다.
- `WEB_FAKE_RUNNER=true`로 LLM 호출 없이 전체 흐름을 검증할 수 있다.
- 가격 데이터는 yfinance를 5분 TTL 캐시로 호출한다. 오프라인이면 차트가 비어 보일 수 있다.
```

- [ ] **Step 2: 백엔드 수동 검증 시나리오**

별도 터미널 두 개에서:

```bash
# 1) backend (fake runner)
WEB_FAKE_RUNNER=true uv run uvicorn tradingagents_web.main:app --reload --port 8000

# 2) frontend
cd web && npm run dev
```

체크리스트:

- [ ] http://localhost:3000/portfolio: AAPL 추가 후 표에 노출. monitor 토글 ON → 좌측 모니터 칸 활성. `sqlite3 tradingagents_web.db 'select source, ticker, cron_expr from schedules'` → `holding|AAPL|30 16 * * 1-5` 행 확인.
- [ ] http://localhost:3000/schedules: AAPL holding-source 스케줄이 노출. `Run now` 클릭 → 토스트 없이 즉시 완료, `/history`에서 새 분석 확인.
- [ ] http://localhost:3000/schedules/new: 다중 티커 입력(`NVDA AMD`)으로 스케줄 2건 생성됨.
- [ ] http://localhost:3000/portfolio/AAPL: 차트와 분석 히스토리, 시그널 마커 노출.
- [ ] 대시보드(`/`): 메트릭 카드 + 보유 종목 시그널 테이블 노출.
- [ ] monitor OFF 후 `schedules`에서 해당 행 사라짐 확인.

- [ ] **Step 3: 빌드 검증**

```bash
cd web && npm run build
uv run pytest tests/web -v
```

Expected: 둘 다 성공.

- [ ] **Step 4: 커밋**

```bash
git add DEV.md
git commit -m "docs(web): document M3 portfolio + schedules workflow"
```

---

## 자가 점검 (Self-Review)

본 plan이 spec §11(M3) "보유 종목 + APScheduler 자동 분석"을 얼마나 충실히 구현하는지 확인:

| spec 요구 | 구현 task |
|---|---|
| §2 S3 (보유 종목 자동 모니터링) | Task 1, 6, 7, 10 (holdings.monitor_enabled → schedule + scheduler 자동 등록) |
| §2 S4 (사용자 정의 스케줄) | Task 8 (schedules CRUD), Task 17 (`/schedules/new`) |
| §3 라우트 `/portfolio` | Task 14 |
| §3 라우트 `/portfolio/:ticker` | Task 15 (가격 차트 + 시그널 + 히스토리) |
| §3 라우트 `/schedules`, `/schedules/new` | Task 16, 17 |
| §3 Dashboard | Task 18 |
| §6 holdings 테이블 | Task 1 |
| §6 schedules 테이블 | Task 1 |
| §6 analyses.schedule_id FK | Task 1 (모델), Task 5 (start_analysis_run에서 채움) |
| §11 M3 알림은 M4로 이월 | (out-of-scope 명시) |

특이 결정:
- holdings.monitor_enabled 토글 시 Schedule 행을 직접 생성/삭제 (`source="holding"` + `holding_id`). 이는 source-of-truth 일원화 + UI에서 동일한 SchedulesTable로 노출 가능.
- `next_run`은 DB에 캐시하지 않고 `_hydrate()`에서 매 응답 시 SchedulerService에서 읽는다. APScheduler가 정확한 timezone-aware 계산을 책임진다.
- 다중 티커 스케줄은 프런트가 N개의 single-ticker 행으로 분할해 생성한다 (백엔드 단순화).
