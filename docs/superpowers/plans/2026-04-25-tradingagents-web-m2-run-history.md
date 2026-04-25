# TradingAgents Web — M2 Run/History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 사용자가 `/run`에서 분석을 시작하고 `/run/:id`에서 SSE 라이브 스트림을 보고, `/history`에서 과거 분석 목록·상세를 조회할 수 있게 한다. 분석 결과는 `analyses` 테이블에 영구 저장된다.

**Architecture:** FastAPI `BackgroundTasks`로 `TradingAgentsGraph.stream()`을 비동기 실행한다. 노드별 chunk를 in-memory 이벤트 버스(asyncio.Queue + ring buffer)에 push하고 `sse-starlette`이 `/api/runs/{id}/stream`으로 브로드캐스트한다. 최종 결과는 SQLite `analyses` 행에 JSON으로 누적 저장. 프런트는 `/run` 폼 → POST → `/run/:id`로 라우팅, `EventSource`로 라이브 패널을 채운다. `/history`는 TanStack Query로 페이지네이션·필터링.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, alembic, sse-starlette, LangGraph(기존), pytest. Next.js 14 App Router, TypeScript, TanStack Query, EventSource(브라우저 native).

**Spec:** [docs/superpowers/specs/2026-04-25-tradingagents-web-design.md](../specs/2026-04-25-tradingagents-web-design.md) — §3, §5.4, §6, §11(M2)

**Out of scope (다른 플랜에서):**
- 비교 뷰 `/history/compare` (M5 폴리싱)
- Portfolio·Schedules·Alerts (M3, M4)
- LLM provider/data vendor 설정 UI (`/settings/*`) — M2는 기본 config 사용
- 비용 한도, 토큰 카운트 정밀 측정 (M5)

**의존 결정 (Open issues §14에 대한 해결):**

1. **노드 출력 인터셉트 지점** → `graph.stream(init_state)` 직접 호출. chunk dict의 키가 노드명, 값이 그 노드의 새 state이므로 거기서 "어느 에이전트가 무엇을 추가했는지" 도출.
2. **세션 저장소** → 이미 M1에서 DB-backed sessions 채택. M2에는 영향 없음.
3. **토큰 카운트** → M2는 LangChain `BaseCallbackHandler.on_llm_end` 훅으로 `usage_metadata`만 누적. 비용 계산은 M5.
4. **alembic 워크플로우** → `alembic upgrade head`를 앱 부팅 시 자동 실행. 새 revision은 매 마일스톤마다 추가 (M2는 `0002`).

---

## File Structure

신규 백엔드:

```
tradingagents_web/
├── models/
│   └── analysis.py          # Analysis ORM
├── schemas/                 # Pydantic schemas (신규 패키지)
│   ├── __init__.py
│   └── analysis.py
├── services/
│   ├── event_bus.py         # in-memory pub/sub (asyncio.Queue)
│   ├── runner.py            # TradingAgentsGraph 실행 + 이벤트 emit
│   └── run_factory.py       # real vs fake runner 선택 (테스트/개발용)
└── api/
    └── runs.py              # POST/GET/DELETE /api/runs, GET stream

migrations/versions/
└── 0002_analyses.py

tests/web/
├── test_event_bus.py
├── test_runner_fake.py
├── test_runs_api.py
└── test_runs_stream.py
```

신규 프런트엔드:

```
web/
├── app/
│   ├── providers.tsx                       # React Query provider
│   ├── (workspace)/
│   │   ├── run/
│   │   │   ├── page.tsx                    # 폼
│   │   │   └── [id]/
│   │   │       └── page.tsx                # 라이브 스트림
│   │   └── history/
│   │       ├── page.tsx                    # 목록
│   │       └── [id]/
│   │           └── page.tsx                # 상세
├── components/
│   ├── shared/
│   │   └── signal-badge.tsx
│   ├── analysis/
│   │   ├── agent-card.tsx
│   │   ├── progress-gauge.tsx
│   │   └── verdict-card.tsx
│   ├── run/
│   │   └── run-form.tsx
│   ├── history/
│   │   ├── history-table.tsx
│   │   └── history-filters.tsx
│   └── ui/
│       ├── badge.tsx                       # shadcn
│       ├── select.tsx                      # shadcn
│       ├── checkbox.tsx                    # shadcn
│       └── skeleton.tsx                    # shadcn
├── hooks/
│   ├── use-runs.ts
│   └── use-run-stream.ts
└── lib/
    ├── sse.ts
    └── runs.ts                             # API 타입 + fetch 래퍼
```

기존 변경:

- `pyproject.toml`: `sse-starlette>=2.1` 추가
- `tradingagents_web/main.py`: `runs` 라우터 등록 + `lifespan`에서 alembic upgrade
- `tradingagents_web/config.py`: `fake_runner: bool` 추가
- `tradingagents_web/models/__init__.py`: `Analysis` export
- `web/app/layout.tsx`: `<Providers>` 래퍼 추가
- `web/components/nav/sidebar.tsx`: 활성 경로 매칭은 그대로
- `web/package.json`: 추가 shadcn 의존성 (`@radix-ui/react-select`, `@radix-ui/react-checkbox`)
- `DEV.md`: M2 사용 절차 단락 추가

---

## Task 1: Analysis 모델 + alembic 마이그레이션

**Files:**
- Create: `tradingagents_web/models/analysis.py`
- Modify: `tradingagents_web/models/__init__.py`
- Create: `migrations/versions/0002_analyses.py`
- Create: `tests/web/test_models_analysis.py`

- [ ] **Step 1: 실패하는 모델 테스트 작성**

`tests/web/test_models_analysis.py`:

```python
"""Tests for Analysis ORM model."""
from datetime import date, datetime, timezone

from tradingagents_web.models import Analysis


def test_analysis_minimal_fields(app_with_test_db):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        a = Analysis(
            run_id="00000000-0000-0000-0000-000000000001",
            ticker="AAPL",
            analysis_date=date(2026, 4, 25),
            status="running",
            llm_provider="openai",
            llm_deep_model="gpt-5.5",
            llm_quick_model="gpt-5.4-mini",
            debate_rounds=1,
            analysts=["market", "news", "fundamentals", "social"],
        )
        db.add(a)
        db.commit()
        db.refresh(a)
        assert a.id > 0
        assert a.created_at is not None
        assert a.completed_at is None
        assert a.decision is None
        assert a.final_state is None
    finally:
        db.close()


def test_analysis_completed_with_state(app_with_test_db):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        a = Analysis(
            run_id="00000000-0000-0000-0000-000000000002",
            ticker="NVDA",
            analysis_date=date(2026, 4, 25),
            status="completed",
            decision="BUY",
            confidence=0.78,
            llm_provider="openai",
            llm_deep_model="gpt-5.5",
            llm_quick_model="gpt-5.4-mini",
            debate_rounds=1,
            analysts=["market"],
            final_state={"market_report": "..."},
            completed_at=datetime.now(timezone.utc),
        )
        db.add(a)
        db.commit()
        db.refresh(a)
        assert a.decision == "BUY"
        assert a.final_state["market_report"] == "..."
    finally:
        db.close()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/web/test_models_analysis.py -v`
Expected: ImportError — `Analysis` not in `tradingagents_web.models`.

- [ ] **Step 3: Analysis 모델 작성**

`tradingagents_web/models/analysis.py`:

```python
"""Analysis ORM: stores every analysis run, in-progress and completed."""
from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Date, DateTime, Float, Integer, String, Index
from sqlalchemy.orm import Mapped, mapped_column

from tradingagents_web.models.base import Base, utcnow


class Analysis(Base):
    """A single analysis run (one ticker, one date, one config)."""

    __tablename__ = "analyses"
    __table_args__ = (
        Index("ix_analyses_ticker_created", "ticker", "created_at"),
        Index("ix_analyses_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    ticker: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    analysis_date: Mapped[date] = mapped_column(Date, nullable=False)

    status: Mapped[str] = mapped_column(String(16), nullable=False)  # running|completed|failed|cancelled
    decision: Mapped[str | None] = mapped_column(String(16), nullable=True)  # BUY|SELL|HOLD|OVERWEIGHT|UNDERWEIGHT
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    llm_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    llm_deep_model: Mapped[str] = mapped_column(String(64), nullable=False)
    llm_quick_model: Mapped[str] = mapped_column(String(64), nullable=False)
    debate_rounds: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    analysts: Mapped[list[str]] = mapped_column(JSON, nullable=False)

    final_state: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

`tradingagents_web/models/__init__.py`에 export 추가:

```python
"""ORM model exports."""
from tradingagents_web.models.analysis import Analysis
from tradingagents_web.models.base import Base, TimestampMixin
from tradingagents_web.models.session import Session
from tradingagents_web.models.user import User

__all__ = ["Analysis", "Base", "Session", "TimestampMixin", "User"]
```

- [ ] **Step 4: alembic 마이그레이션 작성**

`migrations/versions/0002_analyses.py`:

```python
"""analyses table

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-25 00:00:01.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analyses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("analysis_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("llm_provider", sa.String(length=32), nullable=False),
        sa.Column("llm_deep_model", sa.String(length=64), nullable=False),
        sa.Column("llm_quick_model", sa.String(length=64), nullable=False),
        sa.Column("debate_rounds", sa.Integer(), nullable=False),
        sa.Column("analysts", sa.JSON(), nullable=False),
        sa.Column("final_state", sa.JSON(), nullable=True),
        sa.Column("error", sa.String(length=2048), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint("uq_analyses_run_id", "analyses", ["run_id"])
    op.create_index("ix_analyses_ticker", "analyses", ["ticker"])
    op.create_index("ix_analyses_ticker_created", "analyses", ["ticker", "created_at"])
    op.create_index("ix_analyses_status", "analyses", ["status"])


def downgrade() -> None:
    op.drop_index("ix_analyses_status", table_name="analyses")
    op.drop_index("ix_analyses_ticker_created", table_name="analyses")
    op.drop_index("ix_analyses_ticker", table_name="analyses")
    op.drop_constraint("uq_analyses_run_id", "analyses", type_="unique")
    op.drop_table("analyses")
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `uv run pytest tests/web/test_models_analysis.py -v`
Expected: 2 passed.

- [ ] **Step 6: 마이그레이션 검증 (down/up)**

Run:

```bash
rm -f /tmp/m2_mig.db
WEB_DATABASE_URL=sqlite:////tmp/m2_mig.db uv run alembic upgrade head
WEB_DATABASE_URL=sqlite:////tmp/m2_mig.db uv run alembic downgrade base
WEB_DATABASE_URL=sqlite:////tmp/m2_mig.db uv run alembic upgrade head
```

Expected: 모든 명령이 에러 없이 종료. `analyses` 테이블이 down 후 사라졌다가 up 후 재생성.

- [ ] **Step 7: 커밋**

```bash
git add tradingagents_web/models/analysis.py tradingagents_web/models/__init__.py migrations/versions/0002_analyses.py tests/web/test_models_analysis.py
git commit -m "feat(web): add Analysis model + 0002 migration"
```

---

## Task 2: Pydantic 스키마

**Files:**
- Create: `tradingagents_web/schemas/__init__.py`
- Create: `tradingagents_web/schemas/analysis.py`
- Create: `tests/web/test_schemas_analysis.py`

- [ ] **Step 1: 실패하는 스키마 테스트 작성**

`tests/web/test_schemas_analysis.py`:

```python
"""Pydantic schema tests."""
from datetime import date

import pytest
from pydantic import ValidationError

from tradingagents_web.schemas.analysis import (
    AnalysisCreateRequest,
    AnalysisListItem,
    Decision,
    Status,
)


def test_create_request_defaults():
    req = AnalysisCreateRequest(ticker="aapl", analysis_date=date(2026, 4, 25))
    assert req.ticker == "AAPL"  # uppercased
    assert req.analysts == ["market", "social", "news", "fundamentals"]
    assert req.debate_rounds == 1


def test_create_request_rejects_blank_ticker():
    with pytest.raises(ValidationError):
        AnalysisCreateRequest(ticker="", analysis_date=date(2026, 4, 25))


def test_create_request_rejects_unknown_analyst():
    with pytest.raises(ValidationError):
        AnalysisCreateRequest(
            ticker="AAPL",
            analysis_date=date(2026, 4, 25),
            analysts=["market", "bogus"],
        )


def test_decision_status_enum_values():
    assert Decision.BUY.value == "BUY"
    assert Status.RUNNING.value == "running"


def test_list_item_serializes():
    item = AnalysisListItem(
        run_id="abc",
        ticker="AAPL",
        analysis_date=date(2026, 4, 25),
        status=Status.COMPLETED,
        decision=Decision.BUY,
        confidence=0.7,
        created_at="2026-04-25T00:00:00Z",
    )
    dumped = item.model_dump()
    assert dumped["decision"] == "BUY"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/web/test_schemas_analysis.py -v`
Expected: ImportError on `tradingagents_web.schemas.analysis`.

- [ ] **Step 3: 스키마 구현**

`tradingagents_web/schemas/__init__.py`:

```python
"""Pydantic schema exports."""
```

`tradingagents_web/schemas/analysis.py`:

```python
"""Pydantic schemas for the analyses API."""
from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


VALID_ANALYSTS = {"market", "social", "news", "fundamentals"}


class Status(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Decision(str, Enum):
    BUY = "BUY"
    OVERWEIGHT = "OVERWEIGHT"
    HOLD = "HOLD"
    UNDERWEIGHT = "UNDERWEIGHT"
    SELL = "SELL"


class AnalysisCreateRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=16)
    analysis_date: date
    analysts: list[str] = Field(
        default_factory=lambda: ["market", "social", "news", "fundamentals"]
    )
    debate_rounds: int = Field(default=1, ge=1, le=5)
    llm_provider: str | None = None
    llm_deep_model: str | None = None
    llm_quick_model: str | None = None

    @field_validator("ticker")
    @classmethod
    def _normalize_ticker(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("ticker must not be blank")
        return v

    @field_validator("analysts")
    @classmethod
    def _validate_analysts(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("at least one analyst required")
        bad = [a for a in v if a not in VALID_ANALYSTS]
        if bad:
            raise ValueError(f"unknown analysts: {bad}")
        return v


class AnalysisListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    ticker: str
    analysis_date: date
    status: Status
    decision: Decision | None = None
    confidence: float | None = None
    created_at: datetime | str
    completed_at: datetime | None = None


class AnalysisDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    ticker: str
    analysis_date: date
    status: Status
    decision: Decision | None
    confidence: float | None
    llm_provider: str
    llm_deep_model: str
    llm_quick_model: str
    debate_rounds: int
    analysts: list[str]
    final_state: dict[str, Any] | None
    error: str | None
    cost_usd: float | None
    created_at: datetime
    completed_at: datetime | None


class AnalysisCreateResponse(BaseModel):
    run_id: str


class AnalysisListResponse(BaseModel):
    items: list[AnalysisListItem]
    total: int
    page: int
    page_size: int
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/web/test_schemas_analysis.py -v`
Expected: 5 passed.

- [ ] **Step 5: 커밋**

```bash
git add tradingagents_web/schemas tests/web/test_schemas_analysis.py
git commit -m "feat(web): add Pydantic schemas for analyses API"
```

---

## Task 3: 인메모리 이벤트 버스

**Files:**
- Create: `tradingagents_web/services/event_bus.py`
- Create: `tests/web/test_event_bus.py`

이벤트 버스 책임: run_id별로 이벤트를 ring buffer에 보관 + asyncio.Queue로 신규 이벤트를 구독자에게 push. 구독자가 늦게 connect해도 누락된 이벤트를 replay할 수 있어야 함.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/web/test_event_bus.py`:

```python
"""Tests for in-memory analysis event bus."""
import asyncio

import pytest

from tradingagents_web.services.event_bus import AnalysisEvent, EventBus


@pytest.mark.asyncio
async def test_publish_then_subscribe_replays_history():
    bus = EventBus()
    bus.publish("run-1", AnalysisEvent(type="agent_message", data={"text": "hello"}))
    bus.publish("run-1", AnalysisEvent(type="progress", data={"step": 1, "total": 5}))

    received: list[AnalysisEvent] = []
    async with bus.subscribe("run-1") as queue:
        # replay first
        for _ in range(2):
            ev = await asyncio.wait_for(queue.get(), 0.5)
            received.append(ev)
    assert [e.type for e in received] == ["agent_message", "progress"]


@pytest.mark.asyncio
async def test_subscribe_receives_live_events():
    bus = EventBus()

    async with bus.subscribe("run-2") as queue:
        bus.publish("run-2", AnalysisEvent(type="agent_message", data={"text": "live"}))
        ev = await asyncio.wait_for(queue.get(), 0.5)
        assert ev.data["text"] == "live"


@pytest.mark.asyncio
async def test_finish_marks_run_done_and_closes_subs():
    bus = EventBus()
    bus.publish("run-3", AnalysisEvent(type="agent_message", data={}))
    async with bus.subscribe("run-3") as queue:
        await asyncio.wait_for(queue.get(), 0.5)
        bus.finish("run-3")
        sentinel = await asyncio.wait_for(queue.get(), 0.5)
        assert sentinel is None  # closed sentinel


def test_publish_caps_history_per_run():
    bus = EventBus(max_buffer=3)
    for i in range(5):
        bus.publish("run-4", AnalysisEvent(type="agent_message", data={"i": i}))
    history = bus.history("run-4")
    assert [e.data["i"] for e in history] == [2, 3, 4]
```

`pyproject.toml`에 이미 pytest-asyncio가 있으므로 marker 사용 가능. `pytest-asyncio` 모드 확인 필요. 자동 모드가 아닌 경우 `tests/web/conftest.py`에 다음을 추가:

```python
import pytest

pytest_plugins = ()


def pytest_collection_modifyitems(config, items):  # noqa: ARG001
    for item in items:
        if asyncio_test := getattr(item.function, "__name__", "").startswith("test_") and "async" in str(item.function):
            item.add_marker(pytest.mark.asyncio)
```

(만약 conftest.py가 이미 적절히 설정돼 있다면 위 블록은 생략. `uv run pytest tests/web/test_event_bus.py -v`로 검증.)

- [ ] **Step 2: pytest-asyncio 모드 설정**

`pyproject.toml` 끝에 다음을 추가 (이미 있으면 스킵):

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `uv run pytest tests/web/test_event_bus.py -v`
Expected: ImportError on `tradingagents_web.services.event_bus`.

- [ ] **Step 4: 이벤트 버스 구현**

`tradingagents_web/services/event_bus.py`:

```python
"""In-memory pub/sub bus for analysis run events.

Each run_id has:
  - a bounded history (ring buffer) so new subscribers replay from the start
  - a set of live asyncio.Queue subscribers receiving fresh events
A None sentinel is enqueued when the run finishes so consumers can stop.
"""
from __future__ import annotations

import asyncio
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import AsyncIterator, Literal


EventType = Literal["agent_message", "progress", "done", "error", "cancelled"]


@dataclass(frozen=True)
class AnalysisEvent:
    type: EventType
    data: dict
    seq: int = field(default=0)


class EventBus:
    """Singleton-ish bus. One process, single user — no cross-worker fanout needed."""

    def __init__(self, max_buffer: int = 500) -> None:
        self._max = max_buffer
        self._history: dict[str, deque[AnalysisEvent]] = {}
        self._subs: dict[str, set[asyncio.Queue]] = {}
        self._counters: dict[str, int] = {}
        self._finished: set[str] = set()

    def publish(self, run_id: str, event: AnalysisEvent) -> AnalysisEvent:
        seq = self._counters.get(run_id, 0) + 1
        self._counters[run_id] = seq
        stamped = AnalysisEvent(type=event.type, data=event.data, seq=seq)

        buf = self._history.setdefault(run_id, deque(maxlen=self._max))
        buf.append(stamped)

        for q in list(self._subs.get(run_id, set())):
            q.put_nowait(stamped)
        return stamped

    def finish(self, run_id: str) -> None:
        self._finished.add(run_id)
        for q in list(self._subs.get(run_id, set())):
            q.put_nowait(None)

    def history(self, run_id: str) -> list[AnalysisEvent]:
        return list(self._history.get(run_id, []))

    def is_finished(self, run_id: str) -> bool:
        return run_id in self._finished

    @asynccontextmanager
    async def subscribe(self, run_id: str) -> AsyncIterator[asyncio.Queue]:
        queue: asyncio.Queue = asyncio.Queue()

        # Replay history first
        for ev in self.history(run_id):
            queue.put_nowait(ev)
        # If already finished, push sentinel after replay
        if self.is_finished(run_id):
            queue.put_nowait(None)

        self._subs.setdefault(run_id, set()).add(queue)
        try:
            yield queue
        finally:
            self._subs.get(run_id, set()).discard(queue)

    def clear(self, run_id: str) -> None:
        """Remove all state for a run (e.g., after persistence flush)."""
        self._history.pop(run_id, None)
        self._counters.pop(run_id, None)
        self._finished.discard(run_id)
        self._subs.pop(run_id, None)


# module-level singleton
_BUS: EventBus | None = None


def get_event_bus() -> EventBus:
    global _BUS
    if _BUS is None:
        _BUS = EventBus()
    return _BUS


def reset_event_bus() -> None:
    """Test helper: drop the singleton."""
    global _BUS
    _BUS = None
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `uv run pytest tests/web/test_event_bus.py -v`
Expected: 4 passed.

- [ ] **Step 6: 커밋**

```bash
git add tradingagents_web/services/event_bus.py tests/web/test_event_bus.py pyproject.toml
git commit -m "feat(web): add in-memory event bus for run streams"
```

---

## Task 4: Runner 추상화 + Fake Runner

Real runner는 `TradingAgentsGraph`를 호출해 LLM 실비용이 들고 외부 API에 의존한다. 테스트와 로컬 데모를 위해 fake runner를 먼저 만들고 인터페이스를 고정한다.

**Files:**
- Create: `tradingagents_web/services/runner.py`
- Create: `tradingagents_web/services/run_factory.py`
- Modify: `tradingagents_web/config.py`
- Create: `tests/web/test_runner_fake.py`

- [ ] **Step 1: 실패하는 테스트**

`tests/web/test_runner_fake.py`:

```python
"""Fake runner emits a deterministic event sequence for tests/dev."""
from datetime import date

import pytest

from tradingagents_web.services.event_bus import EventBus
from tradingagents_web.services.runner import FakeRunner, RunRequest


@pytest.mark.asyncio
async def test_fake_runner_emits_progress_then_done():
    bus = EventBus()
    runner = FakeRunner(bus=bus, delay=0.0)
    req = RunRequest(
        run_id="run-fake-1",
        ticker="AAPL",
        analysis_date=date(2026, 4, 25),
        analysts=["market", "news"],
        debate_rounds=1,
        llm_provider="openai",
        llm_deep_model="gpt-x",
        llm_quick_model="gpt-x-mini",
    )

    result = await runner.run(req)

    types = [e.type for e in bus.history("run-fake-1")]
    assert "agent_message" in types
    assert "progress" in types
    assert types[-1] == "done"
    assert result.decision == "BUY"
    assert result.final_state["market_report"].startswith("Fake market report")


@pytest.mark.asyncio
async def test_fake_runner_finishes_bus():
    bus = EventBus()
    runner = FakeRunner(bus=bus, delay=0.0)
    req = RunRequest(
        run_id="run-fake-2",
        ticker="AAPL",
        analysis_date=date(2026, 4, 25),
        analysts=["market"],
        debate_rounds=1,
        llm_provider="openai",
        llm_deep_model="gpt-x",
        llm_quick_model="gpt-x-mini",
    )
    await runner.run(req)
    assert bus.is_finished("run-fake-2")
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/web/test_runner_fake.py -v`
Expected: ImportError.

- [ ] **Step 3: Runner 구현 (fake + real 분리)**

`tradingagents_web/services/runner.py`:

```python
"""Runner protocol + fake/real implementations.

The runner consumes a RunRequest, emits AnalysisEvents on the bus, and returns a
RunResult capturing the final state. The API layer persists the result to DB.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol

from tradingagents_web.services.event_bus import AnalysisEvent, EventBus

logger = logging.getLogger(__name__)


@dataclass
class RunRequest:
    run_id: str
    ticker: str
    analysis_date: date
    analysts: list[str]
    debate_rounds: int
    llm_provider: str
    llm_deep_model: str
    llm_quick_model: str
    extra_config: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunResult:
    decision: str | None
    confidence: float | None
    final_state: dict[str, Any]
    cost_usd: float | None = None


class Runner(Protocol):
    async def run(self, request: RunRequest) -> RunResult: ...


class FakeRunner:
    """Emits a deterministic event sequence. No LLM calls."""

    def __init__(self, bus: EventBus, delay: float = 0.05) -> None:
        self.bus = bus
        self.delay = delay

    async def run(self, request: RunRequest) -> RunResult:
        rid = request.run_id
        steps = [
            ("market", "Fake market report for {tk}"),
            ("social", "Fake social sentiment for {tk}"),
            ("news", "Fake news summary for {tk}"),
            ("fundamentals", "Fake fundamentals for {tk}"),
            ("research", "Bull/Bear debate concluded — buy thesis stronger"),
            ("trader", "Recommend BUY with conviction 0.78"),
            ("risk", "Risk team aligned: BUY"),
        ]
        active = [s for s in steps if s[0] in request.analysts] + steps[-3:]
        total = len(active)

        try:
            for i, (role, text) in enumerate(active, start=1):
                self.bus.publish(
                    rid,
                    AnalysisEvent(
                        type="agent_message",
                        data={"role": role, "text": text.format(tk=request.ticker)},
                    ),
                )
                self.bus.publish(rid, AnalysisEvent(type="progress", data={"step": i, "total": total}))
                if self.delay:
                    await asyncio.sleep(self.delay)

            final_state = {
                "market_report": f"Fake market report for {request.ticker}",
                "sentiment_report": f"Fake sentiment for {request.ticker}",
                "news_report": f"Fake news for {request.ticker}",
                "fundamentals_report": f"Fake fundamentals for {request.ticker}",
                "investment_plan": "BUY thesis is stronger than bear case",
                "trader_investment_plan": f"Open position in {request.ticker}",
                "final_trade_decision": "BUY",
            }
            decision = "BUY"
            confidence = 0.78

            self.bus.publish(
                rid,
                AnalysisEvent(
                    type="done",
                    data={"decision": decision, "confidence": confidence},
                ),
            )
            return RunResult(decision=decision, confidence=confidence, final_state=final_state)
        finally:
            self.bus.finish(rid)


class RealRunner:
    """Drives the actual TradingAgentsGraph and streams node outputs."""

    def __init__(self, bus: EventBus) -> None:
        self.bus = bus

    async def run(self, request: RunRequest) -> RunResult:
        # Lazy import: keeps web tests fast and avoids loading langgraph for unit tests.
        from tradingagents.default_config import DEFAULT_CONFIG
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        config = dict(DEFAULT_CONFIG)
        config["llm_provider"] = request.llm_provider
        config["deep_think_llm"] = request.llm_deep_model
        config["quick_think_llm"] = request.llm_quick_model
        config["max_debate_rounds"] = request.debate_rounds
        config.update(request.extra_config)

        rid = request.run_id

        def _build_and_stream() -> dict[str, Any]:
            graph_obj = TradingAgentsGraph(
                selected_analysts=request.analysts,
                debug=False,
                config=config,
            )
            init_state = graph_obj.propagator.create_initial_state(
                request.ticker, str(request.analysis_date)
            )
            args = graph_obj.propagator.get_graph_args()

            last_chunk: dict[str, Any] | None = None
            step = 0
            for chunk in graph_obj.graph.stream(init_state, **args):
                # chunk = {node_name: state_delta}
                step += 1
                last_chunk = chunk
                for node, delta in chunk.items():
                    text = _summarize_delta(delta)
                    if text:
                        self.bus.publish(
                            rid,
                            AnalysisEvent(
                                type="agent_message",
                                data={"role": node, "text": text},
                            ),
                        )
                self.bus.publish(rid, AnalysisEvent(type="progress", data={"step": step, "total": 0}))

            # Compose final state from last cumulative chunk's node delta — the LangGraph
            # stream emits per-node deltas, so we maintain a merged view.
            return last_chunk or {}

        try:
            # Run the synchronous stream in a worker thread so we don't block the event loop.
            final_chunk = await asyncio.to_thread(_build_and_stream)
            # Merge: graph.stream returns deltas. We re-invoke once to get the consolidated final state.
            # Simpler: call propagate to get full final_state separately (but that re-runs the graph,
            # which is too expensive). For M2 we only persist what comes through the stream.
            final_state = final_chunk
            decision_text = str(final_state.get("final_trade_decision") or "")
            decision = _extract_decision(decision_text)

            self.bus.publish(
                rid,
                AnalysisEvent(
                    type="done",
                    data={"decision": decision, "confidence": None},
                ),
            )
            return RunResult(decision=decision, confidence=None, final_state=final_state)
        except Exception as exc:  # noqa: BLE001 — surface every failure to the user
            logger.exception("Real runner failed for run_id=%s", rid)
            self.bus.publish(rid, AnalysisEvent(type="error", data={"message": str(exc)}))
            raise
        finally:
            self.bus.finish(rid)


def _summarize_delta(delta: Any) -> str:
    """Pull the most recent message text out of a LangGraph state delta."""
    if not isinstance(delta, dict):
        return ""
    msgs = delta.get("messages")
    if msgs:
        last = msgs[-1]
        return getattr(last, "content", str(last))[:4000]
    for key in ("market_report", "sentiment_report", "news_report",
                "fundamentals_report", "investment_plan",
                "trader_investment_plan", "final_trade_decision"):
        if delta.get(key):
            return f"[{key}] {str(delta[key])[:4000]}"
    return ""


def _extract_decision(text: str) -> str | None:
    upper = text.upper()
    for word in ("BUY", "OVERWEIGHT", "HOLD", "UNDERWEIGHT", "SELL"):
        if word in upper:
            return word
    return None
```

`tradingagents_web/services/run_factory.py`:

```python
"""Pick the runner implementation based on settings."""
from __future__ import annotations

from tradingagents_web.config import Settings
from tradingagents_web.services.event_bus import get_event_bus
from tradingagents_web.services.runner import FakeRunner, RealRunner, Runner


def make_runner(settings: Settings | None = None) -> Runner:
    settings = settings or Settings()
    bus = get_event_bus()
    if settings.fake_runner:
        return FakeRunner(bus=bus, delay=settings.fake_runner_delay_seconds)
    return RealRunner(bus=bus)
```

`tradingagents_web/config.py`에 다음 두 필드 추가 (`misc` 섹션 아래):

```python
    # Runner: when True, use a deterministic fake graph (no LLM cost). Default False.
    fake_runner: bool = False
    fake_runner_delay_seconds: float = 0.0
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/web/test_runner_fake.py -v`
Expected: 2 passed.

- [ ] **Step 5: 커밋**

```bash
git add tradingagents_web/services/runner.py tradingagents_web/services/run_factory.py tradingagents_web/config.py tests/web/test_runner_fake.py
git commit -m "feat(web): add Runner protocol with FakeRunner + RealRunner stub"
```

---

## Task 5: sse-starlette 의존성 + main.py에 runs 라우터 등록

**Files:**
- Modify: `pyproject.toml`
- Modify: `tradingagents_web/main.py`
- Create: `tradingagents_web/api/runs.py` (스텁)

- [ ] **Step 1: 의존성 추가**

`pyproject.toml`의 `[project] dependencies` 알파벳 순서 적절한 위치에 추가:

```toml
    "sse-starlette>=2.1",
```

Run: `uv sync`
Expected: 신규 패키지 설치 완료.

- [ ] **Step 2: 빈 라우터 스텁 작성**

`tradingagents_web/api/runs.py`:

```python
"""Runs API: create, list, fetch, cancel, stream."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/runs", tags=["runs"])
```

- [ ] **Step 3: main.py에 라우터 등록**

`tradingagents_web/main.py`의 `create_app()` 안 `app.include_router(auth_api.router)` 다음 줄에 추가:

```python
    from tradingagents_web.api import runs as runs_api
    app.include_router(runs_api.router)
```

- [ ] **Step 4: 헬스 체크로 검증**

Run: `uv run pytest tests/web/test_health.py -v`
Expected: 기존 health 테스트 그대로 통과.

- [ ] **Step 5: 커밋**

```bash
git add pyproject.toml tradingagents_web/main.py tradingagents_web/api/runs.py
git commit -m "feat(web): wire empty runs router and add sse-starlette dep"
```

---

## Task 6: POST /api/runs (분석 생성 + 백그라운드 시작)

**Files:**
- Modify: `tradingagents_web/api/runs.py`
- Create: `tests/web/test_runs_api.py`

- [ ] **Step 1: 실패하는 테스트**

`tests/web/test_runs_api.py`:

```python
"""API tests for /api/runs."""
from datetime import date

import pytest

from tradingagents_web.auth import create_session
from tradingagents_web.config import Settings
from tradingagents_web.models import Analysis, User
from tradingagents_web.services.event_bus import reset_event_bus


_settings = Settings()


@pytest.fixture(autouse=True)
def _reset_bus():
    reset_event_bus()
    yield
    reset_event_bus()


def _logged_in_client(app_with_test_db, client):
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


def test_create_run_requires_auth(client):
    r = client.post(
        "/api/runs",
        headers={"X-Requested-With": "fetch"},
        json={"ticker": "AAPL", "analysis_date": "2026-04-25"},
    )
    assert r.status_code == 401


def test_create_run_returns_run_id_and_persists(monkeypatch, app_with_test_db, client):
    monkeypatch.setenv("WEB_FAKE_RUNNER", "true")
    monkeypatch.setenv("WEB_FAKE_RUNNER_DELAY_SECONDS", "0")

    client = _logged_in_client(app_with_test_db, client)
    r = client.post(
        "/api/runs",
        headers={"X-Requested-With": "fetch"},
        json={
            "ticker": "aapl",
            "analysis_date": "2026-04-25",
            "analysts": ["market", "news"],
            "debate_rounds": 1,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert "run_id" in body and len(body["run_id"]) > 0

    # Row exists immediately, status begins as 'running'
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        row = db.query(Analysis).filter_by(run_id=body["run_id"]).one()
        assert row.ticker == "AAPL"
        assert row.status in {"running", "completed"}
        assert row.analysts == ["market", "news"]
    finally:
        db.close()


def test_create_run_validates_payload(app_with_test_db, client):
    client = _logged_in_client(app_with_test_db, client)
    r = client.post(
        "/api/runs",
        headers={"X-Requested-With": "fetch"},
        json={"ticker": "", "analysis_date": "2026-04-25"},
    )
    assert r.status_code == 422
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/web/test_runs_api.py::test_create_run_requires_auth -v`
Expected: 404 (라우트 미정의) → 우리는 401을 기대하므로 fail.

- [ ] **Step 3: POST 엔드포인트 구현**

`tradingagents_web/api/runs.py` 전체 교체:

```python
"""Runs API: create, list, fetch, cancel, stream."""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from tradingagents_web.auth import get_current_user, require_xhr
from tradingagents_web.config import Settings
from tradingagents_web.db import SessionLocal, get_db
from tradingagents_web.models import Analysis, User
from tradingagents_web.schemas.analysis import (
    AnalysisCreateRequest,
    AnalysisCreateResponse,
)
from tradingagents_web.services.event_bus import AnalysisEvent, get_event_bus
from tradingagents_web.services.run_factory import make_runner
from tradingagents_web.services.runner import RunRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/runs", tags=["runs"])
_settings = Settings()


def _resolve_models(req: AnalysisCreateRequest, settings: Settings) -> tuple[str, str, str]:
    """Pick LLM provider/models from request, falling back to defaults."""
    from tradingagents.default_config import DEFAULT_CONFIG

    provider = req.llm_provider or DEFAULT_CONFIG["llm_provider"]
    deep = req.llm_deep_model or DEFAULT_CONFIG["deep_think_llm"]
    quick = req.llm_quick_model or DEFAULT_CONFIG["quick_think_llm"]
    return provider, deep, quick


async def _execute_and_persist(run_id: str, request: RunRequest) -> None:
    """Background task: run the analysis and write the final state to DB."""
    runner = make_runner()
    db = SessionLocal()
    try:
        try:
            result = await runner.run(request)
            row = db.query(Analysis).filter_by(run_id=run_id).one()
            row.status = "completed"
            row.decision = result.decision
            row.confidence = result.confidence
            row.final_state = result.final_state
            row.cost_usd = result.cost_usd
            row.completed_at = datetime.now(timezone.utc)
            db.commit()
        except Exception as exc:  # noqa: BLE001 — record any failure
            logger.exception("Run %s failed", run_id)
            row = db.query(Analysis).filter_by(run_id=run_id).one_or_none()
            if row is not None:
                row.status = "failed"
                row.error = str(exc)[:2000]
                row.completed_at = datetime.now(timezone.utc)
                db.commit()
            get_event_bus().publish(
                run_id,
                AnalysisEvent(type="error", data={"message": str(exc)}),
            )
            get_event_bus().finish(run_id)
    finally:
        db.close()


@router.post(
    "",
    response_model=AnalysisCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_run(
    payload: AnalysisCreateRequest,
    background: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> AnalysisCreateResponse:
    settings = Settings()  # re-read so test monkeypatch takes effect
    provider, deep, quick = _resolve_models(payload, settings)

    run_id = str(uuid.uuid4())
    row = Analysis(
        run_id=run_id,
        ticker=payload.ticker,
        analysis_date=payload.analysis_date,
        status="running",
        llm_provider=provider,
        llm_deep_model=deep,
        llm_quick_model=quick,
        debate_rounds=payload.debate_rounds,
        analysts=payload.analysts,
    )
    db.add(row)
    db.commit()

    request = RunRequest(
        run_id=run_id,
        ticker=payload.ticker,
        analysis_date=payload.analysis_date,
        analysts=payload.analysts,
        debate_rounds=payload.debate_rounds,
        llm_provider=provider,
        llm_deep_model=deep,
        llm_quick_model=quick,
    )

    # Run as a fire-and-forget asyncio task so we don't block the response
    # AND so we can stream events to subscribers immediately.
    background.add_task(asyncio.create_task, _execute_and_persist(run_id, request))

    return AnalysisCreateResponse(run_id=run_id)
```

**주의**: `BackgroundTasks.add_task(asyncio.create_task, ...)`는 coroutine을 즉시 스케줄링한다. 단, FastAPI BackgroundTasks는 응답 후 호출되는데 우리는 *응답 전에* 시작하길 원한다. 이를 위해 더 직접적인 방법은:

```python
asyncio.create_task(_execute_and_persist(run_id, request))
```

`background` 파라미터 제거하고 위 라인으로 교체. 위 코드의 background 부분을 다음과 같이 단순화:

```python
@router.post("", response_model=AnalysisCreateResponse, status_code=status.HTTP_201_CREATED)
def create_run(
    payload: AnalysisCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> AnalysisCreateResponse:
    settings = Settings()
    provider, deep, quick = _resolve_models(payload, settings)
    run_id = str(uuid.uuid4())
    row = Analysis(
        run_id=run_id, ticker=payload.ticker, analysis_date=payload.analysis_date,
        status="running", llm_provider=provider, llm_deep_model=deep,
        llm_quick_model=quick, debate_rounds=payload.debate_rounds,
        analysts=payload.analysts,
    )
    db.add(row)
    db.commit()

    request = RunRequest(
        run_id=run_id, ticker=payload.ticker, analysis_date=payload.analysis_date,
        analysts=payload.analysts, debate_rounds=payload.debate_rounds,
        llm_provider=provider, llm_deep_model=deep, llm_quick_model=quick,
    )
    asyncio.create_task(_execute_and_persist(run_id, request))
    return AnalysisCreateResponse(run_id=run_id)
```

- [ ] **Step 4: 테스트 실행**

Run: `uv run pytest tests/web/test_runs_api.py -v`
Expected: 3 passed. (FakeRunner가 즉시 끝나므로 status가 `completed`까지 갈 수 있음 — 테스트는 `running` 또는 `completed` 둘 다 허용)

- [ ] **Step 5: 커밋**

```bash
git add tradingagents_web/api/runs.py tests/web/test_runs_api.py
git commit -m "feat(web): POST /api/runs creates row and starts background task"
```

---

## Task 7: GET /api/runs (목록, 필터, 페이지네이션)

**Files:**
- Modify: `tradingagents_web/api/runs.py`
- Modify: `tests/web/test_runs_api.py` (테스트 추가)

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/web/test_runs_api.py`에 다음을 append:

```python
def _seed_analyses(TestSessionLocal):
    from datetime import date
    from tradingagents_web.models import Analysis

    db = TestSessionLocal()
    try:
        rows = [
            Analysis(run_id="r-1", ticker="AAPL", analysis_date=date(2026, 4, 20),
                     status="completed", decision="BUY", confidence=0.7,
                     llm_provider="openai", llm_deep_model="x", llm_quick_model="y",
                     debate_rounds=1, analysts=["market"]),
            Analysis(run_id="r-2", ticker="NVDA", analysis_date=date(2026, 4, 21),
                     status="completed", decision="SELL", confidence=0.6,
                     llm_provider="openai", llm_deep_model="x", llm_quick_model="y",
                     debate_rounds=1, analysts=["market"]),
            Analysis(run_id="r-3", ticker="AAPL", analysis_date=date(2026, 4, 22),
                     status="running",
                     llm_provider="openai", llm_deep_model="x", llm_quick_model="y",
                     debate_rounds=1, analysts=["market"]),
        ]
        db.add_all(rows)
        db.commit()
    finally:
        db.close()


def test_list_runs_returns_recent_first(app_with_test_db, client):
    _, TestSessionLocal = app_with_test_db
    _seed_analyses(TestSessionLocal)
    client = _logged_in_client(app_with_test_db, client)
    r = client.get("/api/runs", headers={"X-Requested-With": "fetch"})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert body["items"][0]["run_id"] == "r-3"  # most recent created_at first
    assert body["page"] == 1


def test_list_runs_filter_by_ticker(app_with_test_db, client):
    _, TestSessionLocal = app_with_test_db
    _seed_analyses(TestSessionLocal)
    client = _logged_in_client(app_with_test_db, client)
    r = client.get("/api/runs?ticker=AAPL", headers={"X-Requested-With": "fetch"})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert {item["run_id"] for item in body["items"]} == {"r-1", "r-3"}


def test_list_runs_filter_by_status_and_decision(app_with_test_db, client):
    _, TestSessionLocal = app_with_test_db
    _seed_analyses(TestSessionLocal)
    client = _logged_in_client(app_with_test_db, client)
    r = client.get(
        "/api/runs?status=completed&decision=BUY",
        headers={"X-Requested-With": "fetch"},
    )
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["run_id"] == "r-1"


def test_list_runs_pagination(app_with_test_db, client):
    _, TestSessionLocal = app_with_test_db
    _seed_analyses(TestSessionLocal)
    client = _logged_in_client(app_with_test_db, client)
    r = client.get("/api/runs?page=1&page_size=2", headers={"X-Requested-With": "fetch"})
    body = r.json()
    assert len(body["items"]) == 2
    assert body["total"] == 3
```

- [ ] **Step 2: 테스트 실행하여 실패 확인**

Run: `uv run pytest tests/web/test_runs_api.py::test_list_runs_returns_recent_first -v`
Expected: 405 method not allowed.

- [ ] **Step 3: GET 엔드포인트 구현**

`tradingagents_web/api/runs.py` 상단 import에 추가:

```python
from sqlalchemy import desc, select
from tradingagents_web.schemas.analysis import (
    AnalysisCreateRequest,
    AnalysisCreateResponse,
    AnalysisListItem,
    AnalysisListResponse,
)
```

라우터에 다음 핸들러 추가:

```python
@router.get("", response_model=AnalysisListResponse)
def list_runs(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    ticker: str | None = None,
    status_: str | None = None,  # alias 'status' below
    decision: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> AnalysisListResponse:
    page = max(1, page)
    page_size = max(1, min(100, page_size))

    stmt = select(Analysis)
    if ticker:
        stmt = stmt.where(Analysis.ticker == ticker.strip().upper())
    if status_:
        stmt = stmt.where(Analysis.status == status_)
    if decision:
        stmt = stmt.where(Analysis.decision == decision.upper())

    total = db.execute(
        select(Analysis.id).where(*stmt.whereclause.clauses) if stmt.whereclause is not None
        else select(Analysis.id)
    ).all()
    total_count = len(total)

    rows = db.execute(
        stmt.order_by(desc(Analysis.created_at))
        .limit(page_size)
        .offset((page - 1) * page_size)
    ).scalars().all()

    return AnalysisListResponse(
        items=[AnalysisListItem.model_validate(r) for r in rows],
        total=total_count,
        page=page,
        page_size=page_size,
    )
```

`status_` 파라미터를 query 이름 `status`로 노출하기 위해 FastAPI `Query` alias 사용:

```python
from fastapi import Query

# in handler signature:
status_: str | None = Query(default=None, alias="status"),
```

위 두 import + 파라미터 시그니처 수정 후 저장.

- [ ] **Step 4: 테스트 실행**

Run: `uv run pytest tests/web/test_runs_api.py -v`
Expected: 모든 list 테스트 통과.

- [ ] **Step 5: 커밋**

```bash
git add tradingagents_web/api/runs.py tests/web/test_runs_api.py
git commit -m "feat(web): GET /api/runs with ticker/status/decision filters + pagination"
```

---

## Task 8: GET /api/runs/{run_id} (상세)

**Files:**
- Modify: `tradingagents_web/api/runs.py`
- Modify: `tests/web/test_runs_api.py`

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/web/test_runs_api.py`에 append:

```python
def test_get_run_detail_returns_full_state(app_with_test_db, client):
    _, TestSessionLocal = app_with_test_db
    _seed_analyses(TestSessionLocal)
    client = _logged_in_client(app_with_test_db, client)
    r = client.get("/api/runs/r-1", headers={"X-Requested-With": "fetch"})
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"] == "r-1"
    assert body["decision"] == "BUY"
    assert body["analysts"] == ["market"]


def test_get_run_detail_404(app_with_test_db, client):
    client = _logged_in_client(app_with_test_db, client)
    r = client.get("/api/runs/missing", headers={"X-Requested-With": "fetch"})
    assert r.status_code == 404
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/web/test_runs_api.py::test_get_run_detail_returns_full_state -v`
Expected: 404 (라우트 미정의).

- [ ] **Step 3: 핸들러 추가**

`tradingagents_web/api/runs.py`의 import에 `AnalysisDetail` 추가, 라우터에 다음 추가:

```python
@router.get("/{run_id}", response_model=AnalysisDetail)
def get_run(
    run_id: str,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> AnalysisDetail:
    row = db.query(Analysis).filter_by(run_id=run_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return AnalysisDetail.model_validate(row)
```

- [ ] **Step 4: 테스트 실행**

Run: `uv run pytest tests/web/test_runs_api.py -v`
Expected: 모두 통과.

- [ ] **Step 5: 커밋**

```bash
git add tradingagents_web/api/runs.py tests/web/test_runs_api.py
git commit -m "feat(web): GET /api/runs/{run_id} returns full analysis detail"
```

---

## Task 9: GET /api/runs/{run_id}/stream (SSE)

**Files:**
- Modify: `tradingagents_web/api/runs.py`
- Create: `tests/web/test_runs_stream.py`

- [ ] **Step 1: 실패하는 SSE 테스트**

`tests/web/test_runs_stream.py`:

```python
"""SSE stream endpoint test using TestClient.stream()."""
import asyncio
import json
from datetime import date

import pytest

from tradingagents_web.auth import create_session
from tradingagents_web.config import Settings
from tradingagents_web.models import Analysis, User
from tradingagents_web.services.event_bus import (
    AnalysisEvent,
    get_event_bus,
    reset_event_bus,
)


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


def test_stream_replays_history_then_closes_when_finished(app_with_test_db, client):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        db.add(Analysis(
            run_id="r-stream", ticker="AAPL", analysis_date=date(2026, 4, 25),
            status="completed", decision="BUY", confidence=0.7,
            llm_provider="o", llm_deep_model="d", llm_quick_model="q",
            debate_rounds=1, analysts=["market"],
        ))
        db.commit()
    finally:
        db.close()

    bus = get_event_bus()
    bus.publish("r-stream", AnalysisEvent(type="agent_message", data={"text": "hi"}))
    bus.publish("r-stream", AnalysisEvent(type="done", data={"decision": "BUY"}))
    bus.finish("r-stream")

    _login(app_with_test_db, client)

    with client.stream(
        "GET",
        "/api/runs/r-stream/stream",
        headers={"X-Requested-With": "fetch"},
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = b"".join(response.iter_bytes()).decode("utf-8")

    # Two events + close — verify event blocks present
    assert "event: agent_message" in body
    assert "event: done" in body


def test_stream_404_when_run_missing(app_with_test_db, client):
    _login(app_with_test_db, client)
    with client.stream("GET", "/api/runs/none/stream", headers={"X-Requested-With": "fetch"}) as r:
        assert r.status_code == 404


def test_stream_requires_auth(client):
    with client.stream("GET", "/api/runs/x/stream", headers={"X-Requested-With": "fetch"}) as r:
        assert r.status_code == 401
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/web/test_runs_stream.py -v`
Expected: 404 / 405.

- [ ] **Step 3: SSE 엔드포인트 구현**

`tradingagents_web/api/runs.py` 상단 import에 추가:

```python
import json
from sse_starlette.sse import EventSourceResponse
```

라우터에 다음 추가 (반드시 `/{run_id}` 핸들러 *뒤에* 두면 안되고, FastAPI는 path 매칭 우선이므로 순서는 무관하나 명시적으로 분리):

```python
@router.get("/{run_id}/stream")
async def stream_run(
    run_id: str,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
):
    row = db.query(Analysis).filter_by(run_id=run_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Run not found")

    bus = get_event_bus()

    async def gen():
        async with bus.subscribe(run_id) as queue:
            while True:
                ev = await queue.get()
                if ev is None:
                    yield {"event": "close", "data": "{}"}
                    return
                yield {
                    "event": ev.type,
                    "id": str(ev.seq),
                    "data": json.dumps(ev.data, default=str),
                }

    return EventSourceResponse(gen())
```

- [ ] **Step 4: 테스트 실행**

Run: `uv run pytest tests/web/test_runs_stream.py -v`
Expected: 3 passed. (`TestClient.stream`이 SSE를 받아 텍스트 본문 검사)

- [ ] **Step 5: 커밋**

```bash
git add tradingagents_web/api/runs.py tests/web/test_runs_stream.py
git commit -m "feat(web): SSE /api/runs/{id}/stream replays history + live"
```

---

## Task 10: DELETE /api/runs/{run_id} (취소)

M2의 SoT(scope of truth)는 "취소는 best-effort". 실제 graph 호출은 thread에서 돌아가므로 즉시 중단할 수 없다 — 대신 DB status를 `cancelled`로 마크하고 이벤트 버스에 `cancelled`를 emit한다. 클라이언트는 그것을 보고 UI를 닫는다. RealRunner의 thread는 결과적으로 그냥 끝까지 돌고 `_execute_and_persist`는 status가 이미 `cancelled`임을 보고 final_state 덮어쓰기를 스킵한다.

**Files:**
- Modify: `tradingagents_web/api/runs.py`
- Modify: `tests/web/test_runs_api.py`

- [ ] **Step 1: 테스트 추가**

```python
def test_cancel_running_marks_cancelled(app_with_test_db, client):
    from tradingagents_web.services.event_bus import get_event_bus, reset_event_bus
    reset_event_bus()
    _, TestSessionLocal = app_with_test_db
    _seed_analyses(TestSessionLocal)
    client = _logged_in_client(app_with_test_db, client)

    r = client.delete("/api/runs/r-3", headers={"X-Requested-With": "fetch"})
    assert r.status_code == 200

    db = TestSessionLocal()
    try:
        from tradingagents_web.models import Analysis
        row = db.query(Analysis).filter_by(run_id="r-3").one()
        assert row.status == "cancelled"
    finally:
        db.close()


def test_cancel_completed_run_409(app_with_test_db, client):
    _, TestSessionLocal = app_with_test_db
    _seed_analyses(TestSessionLocal)
    client = _logged_in_client(app_with_test_db, client)
    r = client.delete("/api/runs/r-1", headers={"X-Requested-With": "fetch"})
    assert r.status_code == 409
```

- [ ] **Step 2: 핸들러 구현**

```python
@router.delete("/{run_id}")
def cancel_run(
    run_id: str,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> dict[str, bool]:
    row = db.query(Analysis).filter_by(run_id=run_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if row.status != "running":
        raise HTTPException(status_code=409, detail=f"Cannot cancel run in status '{row.status}'")
    row.status = "cancelled"
    row.completed_at = datetime.now(timezone.utc)
    db.commit()

    bus = get_event_bus()
    bus.publish(run_id, AnalysisEvent(type="cancelled", data={}))
    bus.finish(run_id)
    return {"ok": True}
```

또한 `_execute_and_persist`가 완료 시 `cancelled` 상태를 덮어쓰지 않게 가드:

```python
        try:
            result = await runner.run(request)
            row = db.query(Analysis).filter_by(run_id=run_id).one()
            if row.status == "cancelled":
                return  # leave the cancellation in place
            row.status = "completed"
            ...
```

- [ ] **Step 3: 테스트 실행**

Run: `uv run pytest tests/web/test_runs_api.py -v`
Expected: 모두 통과.

- [ ] **Step 4: 커밋**

```bash
git add tradingagents_web/api/runs.py tests/web/test_runs_api.py
git commit -m "feat(web): DELETE /api/runs/{id} marks run cancelled (best-effort)"
```

---

## Task 11: 프런트 — Providers (TanStack Query)

**Files:**
- Create: `web/app/providers.tsx`
- Modify: `web/app/layout.tsx`

- [ ] **Step 1: Providers 컴포넌트 작성**

`web/app/providers.tsx`:

```tsx
"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            refetchOnWindowFocus: false,
            retry: 1,
          },
        },
      }),
  );
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
```

- [ ] **Step 2: layout.tsx에 래핑**

`web/app/layout.tsx` (현재 내용 확인 후 `<body>` 안 children을 `<Providers>`로 감싸기):

```tsx
import "./globals.css";
import { Providers } from "./providers";

export const metadata = {
  title: "TradingAgents",
  description: "Personal AI trading workbench",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
```

(기존 layout.tsx에 폰트 등이 있으면 보존하고 Providers 추가만 적용.)

- [ ] **Step 3: 빌드 검증**

Run: `cd web && npm run typecheck`
Expected: 0 에러.

- [ ] **Step 4: 커밋**

```bash
git add web/app/providers.tsx web/app/layout.tsx
git commit -m "feat(web): wrap app in TanStack Query provider"
```

---

## Task 12: 프런트 — runs API 타입 + lib

**Files:**
- Create: `web/lib/runs.ts`

- [ ] **Step 1: 타입 + fetch 래퍼**

`web/lib/runs.ts`:

```ts
import { api } from "./api";

export type Decision = "BUY" | "OVERWEIGHT" | "HOLD" | "UNDERWEIGHT" | "SELL";
export type RunStatus = "running" | "completed" | "failed" | "cancelled";

export interface RunListItem {
  run_id: string;
  ticker: string;
  analysis_date: string;
  status: RunStatus;
  decision: Decision | null;
  confidence: number | null;
  created_at: string;
  completed_at: string | null;
}

export interface RunDetail extends RunListItem {
  llm_provider: string;
  llm_deep_model: string;
  llm_quick_model: string;
  debate_rounds: number;
  analysts: string[];
  final_state: Record<string, unknown> | null;
  error: string | null;
  cost_usd: number | null;
}

export interface RunListResponse {
  items: RunListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface CreateRunPayload {
  ticker: string;
  analysis_date: string;
  analysts: string[];
  debate_rounds: number;
  llm_provider?: string;
  llm_deep_model?: string;
  llm_quick_model?: string;
}

export const VALID_ANALYSTS = ["market", "social", "news", "fundamentals"] as const;
export type Analyst = (typeof VALID_ANALYSTS)[number];

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export async function createRun(payload: CreateRunPayload): Promise<{ run_id: string }> {
  return api(`${BASE}/api/runs`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listRuns(params: {
  ticker?: string;
  status?: RunStatus;
  decision?: Decision;
  page?: number;
  page_size?: number;
}): Promise<RunListResponse> {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") usp.set(k, String(v));
  }
  const qs = usp.toString();
  return api(`${BASE}/api/runs${qs ? `?${qs}` : ""}`);
}

export async function getRun(runId: string): Promise<RunDetail> {
  return api(`${BASE}/api/runs/${runId}`);
}

export async function cancelRun(runId: string): Promise<{ ok: boolean }> {
  return api(`${BASE}/api/runs/${runId}`, { method: "DELETE" });
}
```

- [ ] **Step 2: typecheck**

Run: `cd web && npm run typecheck`
Expected: 0 에러.

- [ ] **Step 3: 커밋**

```bash
git add web/lib/runs.ts
git commit -m "feat(web): add runs API client + types"
```

---

## Task 13: 프런트 — useRuns / useRun TanStack Query 훅

**Files:**
- Create: `web/hooks/use-runs.ts`

- [ ] **Step 1: 훅 작성**

`web/hooks/use-runs.ts`:

```ts
"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  cancelRun,
  createRun,
  CreateRunPayload,
  Decision,
  getRun,
  listRuns,
  RunStatus,
} from "@/lib/runs";

export function useRunList(params: {
  ticker?: string;
  status?: RunStatus;
  decision?: Decision;
  page?: number;
  page_size?: number;
}) {
  return useQuery({
    queryKey: ["runs", params],
    queryFn: () => listRuns(params),
  });
}

export function useRun(runId: string | undefined) {
  return useQuery({
    queryKey: ["run", runId],
    queryFn: () => getRun(runId!),
    enabled: !!runId,
    refetchInterval: (q) => {
      const data = q.state.data as { status?: string } | undefined;
      return data?.status === "running" ? 5000 : false;
    },
  });
}

export function useCreateRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateRunPayload) => createRun(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["runs"] }),
  });
}

export function useCancelRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (runId: string) => cancelRun(runId),
    onSuccess: (_d, runId) => {
      qc.invalidateQueries({ queryKey: ["run", runId] });
      qc.invalidateQueries({ queryKey: ["runs"] });
    },
  });
}
```

- [ ] **Step 2: 커밋**

```bash
git add web/hooks/use-runs.ts
git commit -m "feat(web): add TanStack Query hooks for runs"
```

---

## Task 14: 프런트 — SSE 헬퍼 + use-run-stream 훅

**Files:**
- Create: `web/lib/sse.ts`
- Create: `web/hooks/use-run-stream.ts`

- [ ] **Step 1: SSE 헬퍼**

`web/lib/sse.ts`:

```ts
export type SseHandlers = {
  onEvent?: (type: string, data: unknown, raw: MessageEvent) => void;
  onError?: (err: Event) => void;
  onClose?: () => void;
};

const TYPES = ["agent_message", "progress", "done", "error", "cancelled", "close"] as const;

export function openRunStream(runId: string, handlers: SseHandlers): () => void {
  const url = `/api/runs/${encodeURIComponent(runId)}/stream`;
  // EventSource cannot send custom headers — middleware allows /api/* through.
  // Server cookie auth still applies (browser sends it automatically).
  const es = new EventSource(url, { withCredentials: true });

  for (const t of TYPES) {
    es.addEventListener(t, (raw) => {
      let parsed: unknown = null;
      try {
        parsed = JSON.parse((raw as MessageEvent).data);
      } catch {
        parsed = (raw as MessageEvent).data;
      }
      handlers.onEvent?.(t, parsed, raw as MessageEvent);
      if (t === "close") {
        es.close();
        handlers.onClose?.();
      }
    });
  }
  es.onerror = (e) => handlers.onError?.(e);

  return () => es.close();
}
```

- [ ] **Step 2: use-run-stream 훅**

`web/hooks/use-run-stream.ts`:

```ts
"use client";
import { useEffect, useReducer, useRef } from "react";
import { openRunStream } from "@/lib/sse";

export interface AgentMessage {
  role: string;
  text: string;
  seq: number;
}

export interface RunStreamState {
  messages: AgentMessage[];
  step: number;
  total: number;
  done: boolean;
  decision: string | null;
  confidence: number | null;
  error: string | null;
  cancelled: boolean;
}

const init: RunStreamState = {
  messages: [],
  step: 0,
  total: 0,
  done: false,
  decision: null,
  confidence: null,
  error: null,
  cancelled: false,
};

type Action =
  | { kind: "msg"; payload: AgentMessage }
  | { kind: "progress"; step: number; total: number }
  | { kind: "done"; decision: string | null; confidence: number | null }
  | { kind: "error"; message: string }
  | { kind: "cancelled" };

function reducer(s: RunStreamState, a: Action): RunStreamState {
  switch (a.kind) {
    case "msg":
      return { ...s, messages: [...s.messages, a.payload] };
    case "progress":
      return { ...s, step: a.step, total: a.total || s.total };
    case "done":
      return { ...s, done: true, decision: a.decision, confidence: a.confidence };
    case "error":
      return { ...s, error: a.message, done: true };
    case "cancelled":
      return { ...s, cancelled: true, done: true };
  }
}

export function useRunStream(runId: string | undefined): RunStreamState {
  const [state, dispatch] = useReducer(reducer, init);
  const seqRef = useRef(0);

  useEffect(() => {
    if (!runId) return;
    const close = openRunStream(runId, {
      onEvent: (type, data, raw) => {
        const seq = Number(raw.lastEventId || ++seqRef.current);
        if (type === "agent_message") {
          const d = data as { role?: string; text?: string };
          dispatch({
            kind: "msg",
            payload: { role: d.role ?? "agent", text: d.text ?? "", seq },
          });
        } else if (type === "progress") {
          const d = data as { step?: number; total?: number };
          dispatch({ kind: "progress", step: d.step ?? 0, total: d.total ?? 0 });
        } else if (type === "done") {
          const d = data as { decision?: string | null; confidence?: number | null };
          dispatch({
            kind: "done",
            decision: d.decision ?? null,
            confidence: d.confidence ?? null,
          });
        } else if (type === "error") {
          const d = data as { message?: string };
          dispatch({ kind: "error", message: d.message ?? "Unknown error" });
        } else if (type === "cancelled") {
          dispatch({ kind: "cancelled" });
        }
      },
    });
    return () => close();
  }, [runId]);

  return state;
}
```

- [ ] **Step 3: typecheck**

Run: `cd web && npm run typecheck`
Expected: 0 에러.

- [ ] **Step 4: 커밋**

```bash
git add web/lib/sse.ts web/hooks/use-run-stream.ts
git commit -m "feat(web): SSE helper + use-run-stream hook"
```

---

## Task 15: 프런트 — 공유 컴포넌트 (SignalBadge, AgentCard, VerdictCard, ProgressGauge)

**Files:**
- Create: `web/components/shared/signal-badge.tsx`
- Create: `web/components/analysis/agent-card.tsx`
- Create: `web/components/analysis/verdict-card.tsx`
- Create: `web/components/analysis/progress-gauge.tsx`

- [ ] **Step 1: SignalBadge**

`web/components/shared/signal-badge.tsx`:

```tsx
import { cn } from "@/lib/utils";

type Decision = "BUY" | "OVERWEIGHT" | "HOLD" | "UNDERWEIGHT" | "SELL" | null;

const STYLES: Record<Exclude<Decision, null>, string> = {
  BUY: "bg-signal-buy/15 text-signal-buy",
  OVERWEIGHT: "bg-signal-buy/15 text-signal-buy",
  HOLD: "bg-signal-hold/15 text-signal-hold",
  UNDERWEIGHT: "bg-signal-sell/15 text-signal-sell",
  SELL: "bg-signal-sell/15 text-signal-sell",
};

export function SignalBadge({
  decision,
  className,
}: {
  decision: Decision;
  className?: string;
}) {
  if (!decision) {
    return (
      <span
        className={cn(
          "px-1.5 py-0.5 rounded text-[10px] font-mono uppercase tracking-wider bg-bg-2 text-text-3",
          className,
        )}
      >
        —
      </span>
    );
  }
  return (
    <span
      className={cn(
        "px-1.5 py-0.5 rounded text-[10px] font-mono uppercase tracking-wider",
        STYLES[decision],
        className,
      )}
    >
      {decision}
    </span>
  );
}
```

- [ ] **Step 2: AgentCard**

`web/components/analysis/agent-card.tsx`:

```tsx
import { cn } from "@/lib/utils";

const ROLE_STYLES: Record<string, string> = {
  market: "border-l-accent",
  social: "border-l-accent",
  news: "border-l-accent",
  fundamentals: "border-l-accent",
  research: "border-l-signal-buy",
  trader: "border-l-signal-hold",
  risk: "border-l-signal-sell",
};

export function AgentCard({
  role,
  text,
  ts,
}: {
  role: string;
  text: string;
  ts?: string | number;
}) {
  return (
    <div
      className={cn(
        "border border-border-1 border-l-2 bg-bg-1 rounded-md px-3 py-2",
        ROLE_STYLES[role] ?? "border-l-text-3",
      )}
    >
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] uppercase tracking-widest text-text-3 font-medium">
          {role}
        </span>
        {ts && <span className="text-[10px] font-num text-text-3">{ts}</span>}
      </div>
      <pre className="text-xs text-text-2 whitespace-pre-wrap font-sans leading-snug">
        {text}
      </pre>
    </div>
  );
}
```

- [ ] **Step 3: VerdictCard**

`web/components/analysis/verdict-card.tsx`:

```tsx
import { SignalBadge } from "@/components/shared/signal-badge";

type Decision = "BUY" | "OVERWEIGHT" | "HOLD" | "UNDERWEIGHT" | "SELL" | null;

export function VerdictCard({
  decision,
  confidence,
  preliminary = false,
}: {
  decision: Decision;
  confidence: number | null;
  preliminary?: boolean;
}) {
  return (
    <div className="rounded-lg border border-border-1 bg-gradient-to-br from-bg-1 to-bg-2 px-5 py-4">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[10px] uppercase tracking-widest text-text-3">
          {preliminary ? "Preliminary" : "Verdict"}
        </span>
      </div>
      <div className="flex items-baseline gap-3">
        <SignalBadge decision={decision} className="text-lg px-3 py-1" />
        {confidence !== null && (
          <span className="text-sm font-num text-text-2">
            confidence {(confidence * 100).toFixed(0)}%
          </span>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: ProgressGauge**

`web/components/analysis/progress-gauge.tsx`:

```tsx
export function ProgressGauge({ step, total }: { step: number; total: number }) {
  const pct = total > 0 ? Math.min(100, Math.round((step / total) * 100)) : 0;
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] uppercase tracking-widest text-text-3">Progress</span>
        <span className="text-[10px] font-num text-text-2">
          {step}/{total || "?"} · {pct}%
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-bg-2 overflow-hidden">
        <div
          className="h-full bg-accent transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 5: typecheck + 커밋**

Run: `cd web && npm run typecheck`
Expected: 0 에러.

```bash
git add web/components/shared/signal-badge.tsx web/components/analysis/
git commit -m "feat(web): add SignalBadge, AgentCard, VerdictCard, ProgressGauge"
```

---

## Task 16: 프런트 — Run 폼 페이지 `/run`

**Files:**
- Create: `web/app/(workspace)/run/page.tsx`
- Create: `web/components/run/run-form.tsx`

- [ ] **Step 1: RunForm 컴포넌트**

`web/components/run/run-form.tsx`:

```tsx
"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useCreateRun } from "@/hooks/use-runs";
import { Analyst, VALID_ANALYSTS } from "@/lib/runs";

const today = () => new Date().toISOString().slice(0, 10);

export function RunForm() {
  const router = useRouter();
  const create = useCreateRun();

  const [ticker, setTicker] = useState("");
  const [analysisDate, setAnalysisDate] = useState(today());
  const [analysts, setAnalysts] = useState<Analyst[]>([...VALID_ANALYSTS]);
  const [debateRounds, setDebateRounds] = useState(1);

  const toggle = (a: Analyst) =>
    setAnalysts((cur) => (cur.includes(a) ? cur.filter((x) => x !== a) : [...cur, a]));

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ticker.trim() || analysts.length === 0) return;
    const { run_id } = await create.mutateAsync({
      ticker: ticker.trim().toUpperCase(),
      analysis_date: analysisDate,
      analysts,
      debate_rounds: debateRounds,
    });
    router.push(`/run/${run_id}`);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>New Analysis</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="grid gap-4">
          <div className="grid gap-1.5">
            <Label htmlFor="ticker">Ticker</Label>
            <Input
              id="ticker"
              value={ticker}
              onChange={(e) => setTicker(e.target.value)}
              placeholder="AAPL"
              className="font-num uppercase"
              required
            />
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="date">Analysis date</Label>
            <Input
              id="date"
              type="date"
              value={analysisDate}
              onChange={(e) => setAnalysisDate(e.target.value)}
              required
            />
          </div>

          <div className="grid gap-1.5">
            <Label>Analysts</Label>
            <div className="grid grid-cols-2 gap-2">
              {VALID_ANALYSTS.map((a) => (
                <label
                  key={a}
                  className="flex items-center gap-2 rounded-md border border-border-1 bg-bg-1 px-3 py-2 cursor-pointer hover:bg-bg-2"
                >
                  <input
                    type="checkbox"
                    checked={analysts.includes(a)}
                    onChange={() => toggle(a)}
                    className="accent-accent"
                  />
                  <span className="text-xs capitalize">{a}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="rounds">Debate rounds</Label>
            <Input
              id="rounds"
              type="number"
              min={1}
              max={5}
              value={debateRounds}
              onChange={(e) => setDebateRounds(Number(e.target.value))}
            />
          </div>

          {create.error && (
            <p className="text-xs text-signal-sell">
              {(create.error as Error).message}
            </p>
          )}

          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "Starting…" : "Run"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: 페이지**

`web/app/(workspace)/run/page.tsx`:

```tsx
import { RunForm } from "@/components/run/run-form";

export default function RunPage() {
  return (
    <div className="px-4 md:px-6 py-6 md:py-8 max-w-screen-md mx-auto">
      <h1 className="text-xl font-bold text-text-1 mb-1">Run Analysis</h1>
      <p className="text-xs text-text-3 mb-6">Pick a ticker and analyst mix</p>
      <RunForm />
    </div>
  );
}
```

- [ ] **Step 3: typecheck**

Run: `cd web && npm run typecheck`
Expected: 0 에러.

- [ ] **Step 4: 커밋**

```bash
git add web/app/\(workspace\)/run/page.tsx web/components/run/run-form.tsx
git commit -m "feat(web): /run page with new-analysis form"
```

---

## Task 17: 프런트 — Run Live 페이지 `/run/[id]`

**Files:**
- Create: `web/app/(workspace)/run/[id]/page.tsx`

- [ ] **Step 1: 페이지 작성**

`web/app/(workspace)/run/[id]/page.tsx`:

```tsx
"use client";
import { useParams } from "next/navigation";

import { AgentCard } from "@/components/analysis/agent-card";
import { ProgressGauge } from "@/components/analysis/progress-gauge";
import { VerdictCard } from "@/components/analysis/verdict-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useCancelRun, useRun } from "@/hooks/use-runs";
import { useRunStream } from "@/hooks/use-run-stream";

type Decision = "BUY" | "OVERWEIGHT" | "HOLD" | "UNDERWEIGHT" | "SELL" | null;

export default function RunLivePage() {
  const params = useParams<{ id: string }>();
  const runId = params.id;
  const detail = useRun(runId);
  const stream = useRunStream(runId);
  const cancel = useCancelRun();

  const isRunning = detail.data?.status === "running" && !stream.done;

  return (
    <div className="px-4 md:px-6 py-6 md:py-8 max-w-screen-xl mx-auto grid gap-4">
      <div className="flex items-baseline justify-between">
        <div>
          <h1 className="text-xl font-bold text-text-1">
            <span className="font-num">{detail.data?.ticker ?? "…"}</span>{" "}
            <span className="text-text-3 text-sm">
              {detail.data?.analysis_date}
            </span>
          </h1>
          <p className="text-xs text-text-3 mt-1">
            {detail.data?.status ?? "loading"} · run {runId.slice(0, 8)}
          </p>
        </div>
        {isRunning && (
          <Button
            variant="outline"
            onClick={() => cancel.mutate(runId)}
            disabled={cancel.isPending}
          >
            Cancel
          </Button>
        )}
      </div>

      <div className="grid gap-4 md:grid-cols-[1fr_2fr]">
        <Card>
          <CardHeader>
            <CardTitle>Status</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3">
            <ProgressGauge step={stream.step} total={stream.total} />
            {stream.error && (
              <p className="text-xs text-signal-sell">{stream.error}</p>
            )}
            {stream.cancelled && (
              <p className="text-xs text-signal-hold">Cancelled</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Agent stream</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 max-h-[60vh] overflow-y-auto">
            {stream.messages.length === 0 && (
              <p className="text-xs text-text-3">Waiting for agents…</p>
            )}
            {stream.messages.map((m) => (
              <AgentCard key={m.seq} role={m.role} text={m.text} />
            ))}
          </CardContent>
        </Card>
      </div>

      <VerdictCard
        decision={(stream.decision ?? detail.data?.decision ?? null) as Decision}
        confidence={stream.confidence ?? detail.data?.confidence ?? null}
        preliminary={!stream.done}
      />
    </div>
  );
}
```

- [ ] **Step 2: typecheck**

Run: `cd web && npm run typecheck`
Expected: 0 에러.

- [ ] **Step 3: 커밋**

```bash
git add web/app/\(workspace\)/run/\[id\]/page.tsx
git commit -m "feat(web): /run/[id] live SSE page with progress and verdict"
```

---

## Task 18: 프런트 — History 목록 `/history`

**Files:**
- Create: `web/app/(workspace)/history/page.tsx`
- Create: `web/components/history/history-table.tsx`
- Create: `web/components/history/history-filters.tsx`

- [ ] **Step 1: HistoryFilters**

`web/components/history/history-filters.tsx`:

```tsx
"use client";
import { Decision, RunStatus } from "@/lib/runs";

export interface FilterState {
  ticker?: string;
  status?: RunStatus;
  decision?: Decision;
}

const STATUSES: RunStatus[] = ["running", "completed", "failed", "cancelled"];
const DECISIONS: Decision[] = ["BUY", "OVERWEIGHT", "HOLD", "UNDERWEIGHT", "SELL"];

export function HistoryFilters({
  value,
  onChange,
}: {
  value: FilterState;
  onChange: (next: FilterState) => void;
}) {
  return (
    <div className="flex flex-wrap items-end gap-3 mb-4">
      <div>
        <div className="text-[10px] uppercase tracking-widest text-text-3 mb-1">
          Ticker
        </div>
        <input
          value={value.ticker ?? ""}
          placeholder="AAPL"
          onChange={(e) =>
            onChange({ ...value, ticker: e.target.value.toUpperCase() || undefined })
          }
          className="bg-bg-1 border border-border-1 rounded-md px-2 py-1 font-num text-xs w-28 uppercase"
        />
      </div>
      <div>
        <div className="text-[10px] uppercase tracking-widest text-text-3 mb-1">
          Status
        </div>
        <select
          value={value.status ?? ""}
          onChange={(e) =>
            onChange({ ...value, status: (e.target.value || undefined) as RunStatus | undefined })
          }
          className="bg-bg-1 border border-border-1 rounded-md px-2 py-1 text-xs"
        >
          <option value="">All</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>
      <div>
        <div className="text-[10px] uppercase tracking-widest text-text-3 mb-1">
          Decision
        </div>
        <select
          value={value.decision ?? ""}
          onChange={(e) =>
            onChange({
              ...value,
              decision: (e.target.value || undefined) as Decision | undefined,
            })
          }
          className="bg-bg-1 border border-border-1 rounded-md px-2 py-1 text-xs"
        >
          <option value="">All</option>
          {DECISIONS.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: HistoryTable**

`web/components/history/history-table.tsx`:

```tsx
"use client";
import Link from "next/link";

import { SignalBadge } from "@/components/shared/signal-badge";
import { RunListItem } from "@/lib/runs";

function fmt(ts: string) {
  return new Date(ts).toLocaleString(undefined, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function HistoryTable({ rows }: { rows: RunListItem[] }) {
  if (rows.length === 0) {
    return (
      <div className="border border-border-1 rounded-md py-12 text-center text-text-3 text-xs">
        No analyses yet.
      </div>
    );
  }
  return (
    <>
      {/* desktop table */}
      <table className="hidden md:table w-full text-xs border-collapse">
        <thead className="text-text-3 uppercase tracking-widest text-[10px]">
          <tr className="border-b border-border-1">
            <th className="text-left py-2 px-3">Ticker</th>
            <th className="text-left py-2 px-3">Date</th>
            <th className="text-left py-2 px-3">Status</th>
            <th className="text-left py-2 px-3">Decision</th>
            <th className="text-right py-2 px-3">Confidence</th>
            <th className="text-right py-2 px-3">Created</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.run_id}
              className="border-b border-border-1 hover:bg-bg-2 transition-colors"
            >
              <td className="py-2 px-3">
                <Link href={`/history/${r.run_id}`} className="font-num font-bold">
                  {r.ticker}
                </Link>
              </td>
              <td className="py-2 px-3 font-num">{r.analysis_date}</td>
              <td className="py-2 px-3 text-text-2">{r.status}</td>
              <td className="py-2 px-3">
                <SignalBadge decision={r.decision} />
              </td>
              <td className="py-2 px-3 text-right font-num">
                {r.confidence !== null ? `${(r.confidence * 100).toFixed(0)}%` : "—"}
              </td>
              <td className="py-2 px-3 text-right text-text-3 font-num">
                {fmt(r.created_at)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* mobile cards */}
      <ul className="grid md:hidden gap-2">
        {rows.map((r) => (
          <li key={r.run_id}>
            <Link
              href={`/history/${r.run_id}`}
              className="block border border-border-1 rounded-md bg-bg-1 px-3 py-2"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-num font-bold">{r.ticker}</span>
                <SignalBadge decision={r.decision} />
              </div>
              <div className="flex items-center justify-between text-[10px] text-text-3">
                <span className="font-num">{r.analysis_date}</span>
                <span>{r.status}</span>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </>
  );
}
```

- [ ] **Step 3: 페이지**

`web/app/(workspace)/history/page.tsx`:

```tsx
"use client";
import { useState } from "react";

import { HistoryFilters, FilterState } from "@/components/history/history-filters";
import { HistoryTable } from "@/components/history/history-table";
import { Button } from "@/components/ui/button";
import { useRunList } from "@/hooks/use-runs";

export default function HistoryPage() {
  const [filters, setFilters] = useState<FilterState>({});
  const [page, setPage] = useState(1);
  const pageSize = 20;
  const q = useRunList({ ...filters, page, page_size: pageSize });

  const total = q.data?.total ?? 0;
  const lastPage = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="px-4 md:px-6 py-6 md:py-8 max-w-screen-xl mx-auto">
      <h1 className="text-xl font-bold text-text-1 mb-1">History</h1>
      <p className="text-xs text-text-3 mb-6">{total} analyses stored</p>

      <HistoryFilters
        value={filters}
        onChange={(f) => {
          setFilters(f);
          setPage(1);
        }}
      />

      {q.isLoading ? (
        <p className="text-xs text-text-3">Loading…</p>
      ) : (
        <HistoryTable rows={q.data?.items ?? []} />
      )}

      {total > pageSize && (
        <div className="flex items-center justify-end gap-2 mt-4">
          <Button
            variant="outline"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            Prev
          </Button>
          <span className="text-xs text-text-3 font-num">
            {page} / {lastPage}
          </span>
          <Button
            variant="outline"
            disabled={page >= lastPage}
            onClick={() => setPage((p) => Math.min(lastPage, p + 1))}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: typecheck**

Run: `cd web && npm run typecheck`
Expected: 0 에러.

- [ ] **Step 5: 커밋**

```bash
git add web/app/\(workspace\)/history/page.tsx web/components/history/
git commit -m "feat(web): /history list with filters + pagination"
```

---

## Task 19: 프런트 — History 상세 `/history/[id]`

**Files:**
- Create: `web/app/(workspace)/history/[id]/page.tsx`

- [ ] **Step 1: 페이지**

`web/app/(workspace)/history/[id]/page.tsx`:

```tsx
"use client";
import { useParams } from "next/navigation";

import { VerdictCard } from "@/components/analysis/verdict-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useRun } from "@/hooks/use-runs";

type Decision = "BUY" | "OVERWEIGHT" | "HOLD" | "UNDERWEIGHT" | "SELL" | null;

const REPORT_FIELDS = [
  ["market_report", "Market"],
  ["sentiment_report", "Sentiment"],
  ["news_report", "News"],
  ["fundamentals_report", "Fundamentals"],
  ["investment_plan", "Researcher Verdict"],
  ["trader_investment_plan", "Trader Plan"],
  ["final_trade_decision", "Final Decision"],
] as const;

export default function HistoryDetailPage() {
  const { id } = useParams<{ id: string }>();
  const q = useRun(id);

  if (q.isLoading) return <p className="p-6 text-xs text-text-3">Loading…</p>;
  if (q.error || !q.data)
    return (
      <p className="p-6 text-xs text-signal-sell">
        {(q.error as Error)?.message ?? "Run not found"}
      </p>
    );

  const a = q.data;
  const state = (a.final_state ?? {}) as Record<string, string | undefined>;

  return (
    <div className="px-4 md:px-6 py-6 md:py-8 max-w-screen-xl mx-auto grid gap-4">
      <div>
        <h1 className="text-xl font-bold text-text-1">
          <span className="font-num">{a.ticker}</span>{" "}
          <span className="text-text-3 text-sm">{a.analysis_date}</span>
        </h1>
        <p className="text-xs text-text-3 mt-1">
          {a.status} · {a.llm_provider} · deep={a.llm_deep_model} · quick={a.llm_quick_model}
        </p>
      </div>

      <VerdictCard
        decision={a.decision as Decision}
        confidence={a.confidence}
      />

      {a.error && (
        <Card>
          <CardHeader>
            <CardTitle>Error</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="text-xs text-signal-sell whitespace-pre-wrap">{a.error}</pre>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-3">
        {REPORT_FIELDS.map(([key, label]) => {
          const value = state[key];
          if (!value) return null;
          return (
            <Card key={key}>
              <CardHeader>
                <CardTitle>{label}</CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="text-xs text-text-2 whitespace-pre-wrap font-sans leading-relaxed">
                  {value}
                </pre>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: typecheck**

Run: `cd web && npm run typecheck`
Expected: 0 에러.

- [ ] **Step 3: 커밋**

```bash
git add web/app/\(workspace\)/history/\[id\]/page.tsx
git commit -m "feat(web): /history/[id] detail view"
```

---

## Task 20: 통합 테스트 — happy path (login → run → history)

**Files:**
- Modify: `tests/web/test_integration_m1.py` 또는 신규 `tests/web/test_integration_m2.py`

- [ ] **Step 1: 테스트 작성**

`tests/web/test_integration_m2.py`:

```python
"""End-to-end happy path for M2: login → create run (fake) → poll until completed → list/detail."""
import time
from datetime import date

import pytest

from tradingagents_web.auth import hash_password
from tradingagents_web.config import Settings
from tradingagents_web.models import User
from tradingagents_web.services.event_bus import reset_event_bus

_settings = Settings()


@pytest.fixture(autouse=True)
def _reset():
    reset_event_bus()
    yield
    reset_event_bus()


def test_full_run_history_flow(monkeypatch, app_with_test_db, client):
    monkeypatch.setenv("WEB_FAKE_RUNNER", "true")
    monkeypatch.setenv("WEB_FAKE_RUNNER_DELAY_SECONDS", "0")

    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        db.add(User(password_hash=hash_password("pw")))
        db.commit()
    finally:
        db.close()

    headers = {"X-Requested-With": "fetch"}

    r = client.post("/api/auth/login", json={"password": "pw"}, headers=headers)
    assert r.status_code == 200

    r = client.post(
        "/api/runs",
        headers=headers,
        json={
            "ticker": "AAPL",
            "analysis_date": str(date(2026, 4, 25)),
            "analysts": ["market", "news"],
            "debate_rounds": 1,
        },
    )
    assert r.status_code == 201
    run_id = r.json()["run_id"]

    # Wait until status moves to completed
    for _ in range(40):
        r = client.get(f"/api/runs/{run_id}", headers=headers)
        if r.json()["status"] == "completed":
            break
        time.sleep(0.05)
    else:
        pytest.fail("Run did not complete in time")

    detail = r.json()
    assert detail["decision"] == "BUY"
    assert detail["final_state"]["market_report"].startswith("Fake market report")

    r = client.get("/api/runs", headers=headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(it["run_id"] == run_id for it in items)
```

- [ ] **Step 2: 테스트 실행**

Run: `uv run pytest tests/web/test_integration_m2.py -v`
Expected: 1 passed.

- [ ] **Step 3: 전체 백엔드 테스트 통과 확인**

Run: `uv run pytest tests/web -v`
Expected: 모든 테스트 통과 (M1 포함).

- [ ] **Step 4: 커밋**

```bash
git add tests/web/test_integration_m2.py
git commit -m "test(web): add M2 happy-path integration test"
```

---

## Task 21: DEV.md 업데이트 + 수동 검증

**Files:**
- Modify: `DEV.md`

- [ ] **Step 1: DEV.md에 M2 섹션 추가**

`DEV.md` 끝에 다음을 append:

```markdown
## M2 — Run/History

### Quick demo (no LLM cost, fake runner)

1. `WEB_FAKE_RUNNER=true uv run uvicorn tradingagents_web.main:app --reload`
2. `cd web && npm run dev`
3. 브라우저에서 `http://localhost:3000`. 로그인 후:
   - `/run`에서 ticker `AAPL`, 분석가 4종 체크 → "Run"
   - `/run/<id>`로 자동 이동, 가짜 진행과 verdict 확인
   - `/history`에서 방금 분석이 목록에 보이는지 확인 → 클릭 → 상세 보고서

### Real run (LLM 비용 발생)

`WEB_FAKE_RUNNER=false`로 두고(기본) 환경변수에 LLM provider 키 설정. M2는 `tradingagents/default_config.py`의 기본 모델을 사용한다. 모델 변경 UI는 M5에서 추가 예정.
```

- [ ] **Step 2: 수동 스모크 (사용자가 실제로 데모 시도)**

Run: `WEB_FAKE_RUNNER=true uv run uvicorn tradingagents_web.main:app --reload --port 8000`
별 터미널: `cd web && NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev`

브라우저에서 위 데모 절차 1회 실행. 콘솔/네트워크 탭에 200 응답과 SSE 이벤트 흐름 확인. (실패 시 해당 task의 step으로 돌아가 디버깅.)

- [ ] **Step 3: 커밋**

```bash
git add DEV.md
git commit -m "docs(web): document M2 dev quickstart"
```

---

## Self-review checklist

(플랜 작성자가 직접 본인 검증)

**1. Spec coverage:**
- §3 routing: `/run`, `/run/:id`, `/history`, `/history/:id` — Tasks 16, 17, 18, 19. ✅ (`/history/compare`는 M5)
- §4 design tokens: 기존 토큰을 사용. ✅
- §5.1 architecture: FastAPI + SQLite + Next.js, in-memory event bus + sse-starlette. ✅
- §5.4 SSE: `agent_message`, `progress`, `done`, `error`, `cancelled`, `close` 이벤트 타입 정의. ✅
- §6.1 analyses table: Task 1 모델/마이그레이션이 모든 필드 포함. ✅ (`schedule_id`는 M3에서 추가)
- §11 M2: Run + History 모두 포함. ✅

**2. Placeholders:** "TBD"/"적절한 에러 처리" 등 placeholder 없음. 모든 step에 실 코드.

**3. Type consistency:**
- `RunListItem`/`RunDetail`/`AnalysisDetail` 필드 일치 (run_id, ticker, status, decision, confidence) ✅
- `EventBus.publish/finish/subscribe/history` 시그니처 일관 ✅
- `Decision` 값 `BUY|OVERWEIGHT|HOLD|UNDERWEIGHT|SELL`로 백엔드/프런트 동일 ✅
- `Status` 값 `running|completed|failed|cancelled` 동일 ✅

**4. Out-of-band 검토:**
- `_execute_and_persist`가 `cancelled` 상태를 보존하도록 가드함 (Task 10) ✅
- `monkeypatch`로 `WEB_FAKE_RUNNER`를 켜는 테스트는 `Settings()`가 매 요청마다 재인스턴스화되도록 라우터에서 보장함 (Task 6) ✅
- SSE는 EventSource가 custom header를 못 보내므로 `X-Requested-With`를 강제하지 않음(읽기 전용 라우트 → CSRF 위험 없음) ✅

---

## Execution Handoff

**1. Subagent-Driven (recommended)** — 매 태스크마다 fresh subagent, 사이사이 리뷰

**2. Inline Execution** — 이 세션에서 batch + 체크포인트

어느 방식으로 진행할까요?
