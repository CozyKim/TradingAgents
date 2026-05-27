# 산업/섹터 분석 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AI · 전력 · 반도체(메모리) · 반도체(비메모리) · 로봇 · 우주 같은 산업을 선택하면 가치사슬을 단계별로 분해하고, 각 단계 핵심 기업의 점유율을 출처와 함께 정리한 다음, 후보 종목을 클릭 한 번으로 기존 `/run` 종목 분석 파이프라인으로 넘기는 산업/섹터 리서치 기능을 추가한다.

**Architecture:** `tradingagents/graph_sector/`에 4단계 LangGraph 그래프(Macro Overview → Value-Chain Map → Competitive Landscape → Investment Outlook)를 새로 만든다. 노드들은 `web_search` 도구(Tavily 래핑 + 호출 횟수 가드)를 통해 근거를 모은다. `tradingagents_web/services/sector_runner.py`가 종목 `RealRunner`와 같은 패턴으로 phase 전이를 `EventBus`에 발행하고, 완료 결과를 `sector_reports`에 버전 단위로 누적한다. 프런트는 `/sectors`(목록), `/sectors/[slug]`(최신 리포트 + 버전), `/sectors/[slug]/runs/[rid]`(SSE 진행)를 추가하고, mermaid 라이브러리를 dynamic import로 가치사슬 다이어그램을 그린다. 리포트의 `candidate_tickers` 카드에서 "Run analysis" 버튼이 `/run?ticker=...&from_sector=...`로 기존 종목 분석 폼에 prefill한다.

**Tech Stack:** Python 3.10+ / FastAPI / Pydantic v2 / SQLAlchemy 2.x / Alembic / LangGraph / langchain-core / tavily-python / pytest / respx · Next.js 14 / React 18 / TypeScript / TanStack Query / mermaid@^11 / Vitest / Playwright

**Spec:** [`docs/superpowers/specs/2026-05-28-sector-industry-analysis-design.md`](../specs/2026-05-28-sector-industry-analysis-design.md)

**Out of scope (다른 마일스톤에서):**
- 자동 cron 트리거(섹터 분석 스케줄러 통합)
- 산업 비교 뷰(섹터 A vs B)
- 사용자 업로드 자료 RAG
- 다국어 리포트 (일단 한국어 단일)
- 산업 리포트 갱신 시 in-app/Telegram 알림

---

## File Structure

신규 백엔드:

```
tradingagents/
└── graph_sector/
    ├── __init__.py
    ├── state.py
    ├── sector_graph.py
    ├── nodes/
    │   ├── __init__.py
    │   ├── macro_overview.py
    │   ├── value_chain.py
    │   ├── competitive_landscape.py
    │   └── investment_outlook.py
    └── tools/
        ├── __init__.py
        └── web_search.py

tradingagents_web/
├── models/
│   ├── sector.py
│   ├── sector_run.py
│   └── sector_report.py
├── schemas/
│   └── sector.py
├── services/
│   ├── sector_runner.py
│   └── sector_fake_runner.py
└── api/
    └── sectors.py

migrations/versions/
└── 2026_05_28_add_sectors.py
```

신규 테스트:

```
tests/
├── graph_sector/
│   ├── test_state.py
│   ├── test_web_search_tool.py
│   ├── test_macro_overview_node.py
│   ├── test_value_chain_node.py
│   ├── test_competitive_node.py
│   ├── test_outlook_node.py
│   └── test_sector_graph.py
└── web/
    ├── test_models_sector.py
    ├── test_sector_runner.py
    ├── test_sector_fake_runner.py
    ├── test_sectors_api.py
    └── test_integration_sector.py
```

신규 프런트:

```
web/
├── app/(workspace)/sectors/
│   ├── page.tsx
│   ├── new/page.tsx
│   └── [slug]/
│       ├── page.tsx
│       └── runs/[rid]/page.tsx
├── components/sector/
│   ├── sector-card.tsx
│   ├── value-chain-diagram.tsx
│   ├── companies-table.tsx
│   ├── candidate-tickers.tsx
│   └── phase-progress.tsx
└── lib/sectors.ts
```

**수정 대상:**

| 경로 | 이유 |
|---|---|
| `pyproject.toml` | `tavily-python>=0.5` 추가 |
| `tradingagents_web/main.py` | sectors 라우터 include |
| `tradingagents_web/models/__init__.py` | 새 모델 export |
| `web/package.json` | `mermaid@^11` 추가 |
| `web/components/nav/sidebar.tsx` | Sectors 메뉴 |
| `web/components/nav/tab-bar.tsx` | Sectors 탭 |
| `web/app/(workspace)/run/page.tsx` | `from_sector` / `from_report` 쿼리 prefill |
| `.env.example` | `TAVILY_API_KEY`, `SECTOR_SEARCH_BUDGET`, `SECTOR_NODE_SEARCH_BUDGET` |
| `DEV.md` | 섹터 분석 셋업·운영 |
| `README.md` | Sectors 섹션 |

---

## Task 1: 워크트리 셋업 + 의존성 추가

**Files:**
- Worktree: `/Users/kimjaehyun/coding/TradingAgents/.worktrees/feat-sector-analysis`
- Modify: `pyproject.toml`
- Modify: `.env.example`

- [ ] **Step 1: 워크트리 생성**

`superpowers:using-git-worktrees` 스킬을 먼저 호출해 격리 환경 마련. 결과는 `.worktrees/feat-sector-analysis` 디렉토리, 브랜치 `feat/sector-analysis`.

- [ ] **Step 2: 워크트리에서 운영 DB 카피 방지**

워크트리 안에서:

```bash
cp ../../.env.test .env  # 또는
echo 'WEB_DATABASE_URL=sqlite:///./worktree.db' > .env
```

DEV.md의 `ALLOW_PROD_DB_IN_WORKTREE` 가드 그대로 작동하는지 `./dev.sh` 한 번 띄워 확인.

- [ ] **Step 3: `pyproject.toml`에 `tavily-python` 추가**

`[project.dependencies]` 섹션:

```toml
"tavily-python>=0.5,<1.0",
```

- [ ] **Step 4: `uv sync`로 락 갱신**

```bash
uv sync
```

`uv.lock`에 `tavily-python` 항목이 추가됐는지 확인.

- [ ] **Step 5: `.env.example`에 신규 키 추가**

```bash
# Tavily (sector analysis web search)
TAVILY_API_KEY=

# Sector analysis search budgets (optional, defaults shown)
# SECTOR_SEARCH_BUDGET=12
# SECTOR_NODE_SEARCH_BUDGET=3
```

- [ ] **Step 6: 커밋**

```bash
git add pyproject.toml uv.lock .env.example
git commit -m "feat(sector): add tavily dependency + env vars"
```

---

## Task 2: DB 모델 — Sector / SectorRun / SectorReport

**Files:**
- Create: `tradingagents_web/models/sector.py`
- Create: `tradingagents_web/models/sector_run.py`
- Create: `tradingagents_web/models/sector_report.py`
- Modify: `tradingagents_web/models/__init__.py`
- Test: `tests/web/test_models_sector.py`

- [ ] **Step 1: 모델 테스트 먼저 작성**

`tests/web/test_models_sector.py`:

```python
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from tradingagents_web.db import SessionLocal
from tradingagents_web.models.sector import Sector
from tradingagents_web.models.sector_report import SectorReport
from tradingagents_web.models.sector_run import SectorRun


def test_sector_unique_slug(db_session):
    db_session.add(Sector(slug="ai", name="AI", keywords=[], is_preset=True))
    db_session.commit()
    db_session.add(Sector(slug="ai", name="dup", keywords=[]))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_sector_report_unique_version_per_sector(db_session):
    sec = Sector(slug="x", name="X", keywords=[])
    db_session.add(sec)
    db_session.flush()
    run1 = SectorRun(id="r1", sector_id=sec.id, status="completed",
                    started_at=datetime.now(timezone.utc),
                    finished_at=datetime.now(timezone.utc))
    run2 = SectorRun(id="r2", sector_id=sec.id, status="completed",
                    started_at=datetime.now(timezone.utc),
                    finished_at=datetime.now(timezone.utc))
    db_session.add_all([run1, run2])
    db_session.flush()
    db_session.add(SectorReport(sector_id=sec.id, run_id="r1", version=1,
                                report_md="", value_chain_mermaid="",
                                companies=[], outlook_summary="",
                                candidate_tickers=[]))
    db_session.add(SectorReport(sector_id=sec.id, run_id="r2", version=1,
                                report_md="", value_chain_mermaid="",
                                companies=[], outlook_summary="",
                                candidate_tickers=[]))
    with pytest.raises(IntegrityError):
        db_session.commit()
```

- [ ] **Step 2: 테스트 실행으로 실패 확인**

```bash
uv run pytest tests/web/test_models_sector.py -v
```

Expected: FAIL — `ModuleNotFoundError` 또는 모델 미정의.

- [ ] **Step 3: `tradingagents_web/models/sector.py` 작성**

```python
"""Sector ORM — 산업/섹터 정의 (프리셋 + 사용자 정의)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tradingagents_web.models.base import Base

if TYPE_CHECKING:
    from tradingagents_web.models.sector_report import SectorReport
    from tradingagents_web.models.sector_run import SectorRun


class Sector(Base):
    __tablename__ = "sectors"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_preset: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    reports: Mapped[list["SectorReport"]] = relationship(
        back_populates="sector", cascade="all, delete-orphan"
    )
    runs: Mapped[list["SectorRun"]] = relationship(
        back_populates="sector", cascade="all, delete-orphan"
    )
```

- [ ] **Step 4: `tradingagents_web/models/sector_run.py` 작성**

```python
"""SectorRun ORM — 산업 분석 실행 1회."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tradingagents_web.models.base import Base

if TYPE_CHECKING:
    from tradingagents_web.models.sector import Sector
    from tradingagents_web.models.sector_report import SectorReport


class SectorRun(Base):
    __tablename__ = "sector_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    sector_id: Mapped[int] = mapped_column(
        ForeignKey("sectors.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(16))  # running|completed|failed
    phase: Mapped[str | None] = mapped_column(String(32), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_quick_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    llm_deep_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    search_call_count: Mapped[int] = mapped_column(Integer, default=0)

    sector: Mapped["Sector"] = relationship(back_populates="runs")
    report: Mapped["SectorReport | None"] = relationship(
        back_populates="run", uselist=False
    )
```

- [ ] **Step 5: `tradingagents_web/models/sector_report.py` 작성**

```python
"""SectorReport ORM — 산업 분석 결과 (버전별 누적)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tradingagents_web.models.base import Base

if TYPE_CHECKING:
    from tradingagents_web.models.sector import Sector
    from tradingagents_web.models.sector_run import SectorRun


class SectorReport(Base):
    __tablename__ = "sector_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    sector_id: Mapped[int] = mapped_column(
        ForeignKey("sectors.id"), index=True
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("sector_runs.id"), unique=True
    )
    version: Mapped[int] = mapped_column(Integer)
    report_md: Mapped[str] = mapped_column(Text)
    value_chain_mermaid: Mapped[str] = mapped_column(Text)
    companies: Mapped[list[dict]] = mapped_column(JSON, default=list)
    outlook_summary: Mapped[str] = mapped_column(Text)
    candidate_tickers: Mapped[list[dict]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    sector: Mapped["Sector"] = relationship(back_populates="reports")
    run: Mapped["SectorRun"] = relationship(back_populates="report")

    __table_args__ = (UniqueConstraint("sector_id", "version"),)
```

- [ ] **Step 6: `tradingagents_web/models/__init__.py`에 export 추가**

기존 `__all__`/import 블록 끝에:

```python
from tradingagents_web.models.sector import Sector  # noqa: F401
from tradingagents_web.models.sector_report import SectorReport  # noqa: F401
from tradingagents_web.models.sector_run import SectorRun  # noqa: F401
```

- [ ] **Step 7: 테스트 통과 확인**

```bash
uv run pytest tests/web/test_models_sector.py -v
```

Expected: PASS.

- [ ] **Step 8: 커밋**

```bash
git add tradingagents_web/models/ tests/web/test_models_sector.py
git commit -m "feat(sector): add Sector/SectorRun/SectorReport ORM models"
```

---

## Task 3: Alembic 마이그레이션 + 6종 프리셋 시드

**Files:**
- Create: `migrations/versions/2026_05_28_add_sectors.py`
- Test: `tests/web/test_models_sector.py`에 마이그레이션 시드 검증 추가

- [ ] **Step 1: 마이그레이션 파일 생성**

```bash
uv run alembic revision -m "add sectors"
```

생성된 파일을 `migrations/versions/2026_05_28_add_sectors.py`로 리네임(혹은 생성된 그대로 사용).

- [ ] **Step 2: 마이그레이션 작성**

```python
"""add sectors

Revision ID: 2026_05_28_add_sectors
Revises: <직전 head>
Create Date: 2026-05-28
"""
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "2026_05_28_add_sectors"
down_revision = "<직전 head>"  # 실제 head로 교체
branch_labels = None
depends_on = None


PRESET_SECTORS = [
    {
        "slug": "ai",
        "name": "AI · 인공지능",
        "description": "AI 가속기·파운데이션 모델·인프라 전반",
        "keywords": ["AI accelerator", "GPU", "foundation models", "NVIDIA", "OpenAI"],
    },
    {
        "slug": "power",
        "name": "전력 · 그리드",
        "description": "AI 데이터센터 전력·송배전·HVDC·트랜스포머",
        "keywords": ["power grid", "transformer", "HVDC", "AI data center power"],
    },
    {
        "slug": "semiconductor-memory",
        "name": "반도체 — 메모리",
        "description": "DRAM·NAND·HBM 메모리 사이클",
        "keywords": ["DRAM", "NAND", "HBM", "Samsung", "SK Hynix", "Micron"],
    },
    {
        "slug": "semiconductor-logic",
        "name": "반도체 — 비메모리",
        "description": "파운드리·팹리스·EUV·소재·장비",
        "keywords": ["foundry", "fabless", "EUV", "TSMC", "ASML", "Applied Materials"],
    },
    {
        "slug": "robotics",
        "name": "로봇",
        "description": "휴머노이드·산업용 로봇",
        "keywords": ["humanoid", "industrial robot", "Boston Dynamics", "Tesla Optimus"],
    },
    {
        "slug": "space",
        "name": "우주",
        "description": "발사체·위성·우주 인프라",
        "keywords": ["launch vehicle", "satellite", "SpaceX", "Rocket Lab", "Starlink"],
    },
]


def upgrade() -> None:
    op.create_table(
        "sectors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("is_preset", sa.Boolean(), nullable=False, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "sector_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("sector_id", sa.Integer(),
                  sa.ForeignKey("sectors.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("phase", sa.String(32), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("llm_quick_model", sa.String(64), nullable=True),
        sa.Column("llm_deep_model", sa.String(64), nullable=True),
        sa.Column("search_call_count", sa.Integer(), nullable=False, default=0),
    )
    op.create_table(
        "sector_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sector_id", sa.Integer(),
                  sa.ForeignKey("sectors.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("run_id", sa.String(36),
                  sa.ForeignKey("sector_runs.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("report_md", sa.Text(), nullable=False),
        sa.Column("value_chain_mermaid", sa.Text(), nullable=False),
        sa.Column("companies", sa.JSON(), nullable=False),
        sa.Column("outlook_summary", sa.Text(), nullable=False),
        sa.Column("candidate_tickers", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("sector_id", "version", name="uq_sector_report_version"),
    )

    # 프리셋 시드
    now = datetime.now(timezone.utc)
    sectors_tbl = sa.table(
        "sectors",
        sa.column("slug", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("keywords", sa.JSON),
        sa.column("is_preset", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        sectors_tbl,
        [
            {
                "slug": p["slug"],
                "name": p["name"],
                "description": p["description"],
                "keywords": p["keywords"],
                "is_preset": True,
                "created_at": now,
            }
            for p in PRESET_SECTORS
        ],
    )


def downgrade() -> None:
    op.drop_table("sector_reports")
    op.drop_table("sector_runs")
    op.drop_table("sectors")
```

`down_revision`의 `<직전 head>`는 `alembic heads`로 조회한 값으로 교체.

- [ ] **Step 3: 마이그레이션 적용**

```bash
uv run alembic upgrade head
```

- [ ] **Step 4: 시드 검증 테스트 추가**

`tests/web/test_models_sector.py`에 추가:

```python
def test_preset_sectors_seeded(db_session):
    slugs = {s.slug for s in db_session.query(Sector).filter_by(is_preset=True).all()}
    assert slugs >= {
        "ai", "power", "semiconductor-memory",
        "semiconductor-logic", "robotics", "space",
    }
```

- [ ] **Step 5: 테스트 통과**

```bash
uv run pytest tests/web/test_models_sector.py -v
```

Expected: PASS.

- [ ] **Step 6: 커밋**

```bash
git add migrations/versions/2026_05_28_add_sectors.py tests/web/test_models_sector.py
git commit -m "feat(sector): migration + 6-preset seed data"
```

---

## Task 4: Pydantic 스키마

**Files:**
- Create: `tradingagents_web/schemas/sector.py`
- Test: `tests/web/test_schemas_sector.py`

- [ ] **Step 1: 스키마 테스트 작성**

`tests/web/test_schemas_sector.py`:

```python
import pytest
from pydantic import ValidationError

from tradingagents_web.schemas.sector import (
    CompanyShare,
    CandidateTicker,
    SectorCreate,
    SectorReportOut,
)


def test_sector_create_slug_auto_from_name():
    s = SectorCreate(name="My Sector", keywords=["a"])
    assert s.slug == "my-sector"


def test_company_share_basis_enum():
    CompanyShare(name="X", stage="Up", share_value=10.0,
                 share_basis="reported", confidence="high", sources=[])
    with pytest.raises(ValidationError):
        CompanyShare(name="X", stage="Up", share_value=10.0,
                     share_basis="guessed", confidence="high", sources=[])


def test_candidate_ticker_required_fields():
    CandidateTicker(ticker="AAPL", name="Apple", stage="Down", reason="...")
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/web/test_schemas_sector.py -v
```

Expected: FAIL.

- [ ] **Step 3: `tradingagents_web/schemas/sector.py` 작성**

```python
"""Pydantic schemas for /api/sectors."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator


def slugify(name: str) -> str:
    """Convert a human name to a URL-safe slug.

    Keeps ASCII letters/digits, replaces non-ASCII and whitespace with '-'.
    Collapses repeated dashes and strips edges.
    """
    s = name.lower()
    s = re.sub(r"[^\w\s-]+", "-", s, flags=re.UNICODE)
    s = re.sub(r"\s+", "-", s.strip())
    s = re.sub(r"-{2,}", "-", s)
    return s.strip("-")


ShareBasis = Literal["reported", "estimated", "unknown"]
Confidence = Literal["high", "medium", "low"]


class CompanyShare(BaseModel):
    name: str
    ticker: str | None = None
    stage: str
    share_value: float = Field(ge=0.0, le=100.0)
    share_basis: ShareBasis
    confidence: Confidence
    sources: list[HttpUrl] = Field(default_factory=list)


class CandidateTicker(BaseModel):
    ticker: str
    name: str
    stage: str
    reason: str


class SectorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    slug: str | None = None
    description: str | None = None
    keywords: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def fill_slug(self) -> "SectorCreate":
        if not self.slug:
            self.slug = slugify(self.name)
        return self


class SectorOut(BaseModel):
    id: int
    slug: str
    name: str
    description: str | None
    keywords: list[str]
    is_preset: bool
    created_at: datetime
    latest_report_version: int | None = None
    latest_report_at: datetime | None = None

    model_config = {"from_attributes": True}


class SectorRunCreate(BaseModel):
    llm_quick_model: str | None = None
    llm_deep_model: str | None = None


class SectorRunOut(BaseModel):
    id: str
    sector_id: int
    status: str
    phase: str | None
    started_at: datetime
    finished_at: datetime | None
    error: str | None
    search_call_count: int

    model_config = {"from_attributes": True}


class SectorReportOut(BaseModel):
    id: int
    sector_id: int
    run_id: str
    version: int
    report_md: str
    value_chain_mermaid: str
    companies: list[CompanyShare]
    outlook_summary: str
    candidate_tickers: list[CandidateTicker]
    created_at: datetime

    model_config = {"from_attributes": True}


class SectorReportSummary(BaseModel):
    id: int
    version: int
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: 테스트 통과**

```bash
uv run pytest tests/web/test_schemas_sector.py -v
```

Expected: PASS.

- [ ] **Step 5: 커밋**

```bash
git add tradingagents_web/schemas/sector.py tests/web/test_schemas_sector.py
git commit -m "feat(sector): pydantic schemas with slug auto-fill + share basis enum"
```

---

## Task 5: `web_search` 도구 + 호출 가드

**Files:**
- Create: `tradingagents/graph_sector/__init__.py`
- Create: `tradingagents/graph_sector/tools/__init__.py`
- Create: `tradingagents/graph_sector/tools/web_search.py`
- Test: `tests/graph_sector/test_web_search_tool.py`

- [ ] **Step 1: 패키지 디렉토리 생성**

```bash
mkdir -p tradingagents/graph_sector/tools tradingagents/graph_sector/nodes
touch tradingagents/graph_sector/__init__.py
touch tradingagents/graph_sector/tools/__init__.py
touch tradingagents/graph_sector/nodes/__init__.py
```

- [ ] **Step 2: 도구 테스트 작성**

`tests/graph_sector/test_web_search_tool.py`:

```python
from unittest.mock import patch, MagicMock

from tradingagents.graph_sector.tools.web_search import (
    SearchBudget,
    make_web_search_tool,
)


def test_budget_exhausted_returns_empty():
    budget = SearchBudget(total=2, per_node=3)
    tool = make_web_search_tool(budget)
    budget.total_used = 2
    result = tool.invoke({"query": "anything"})
    assert result == []


def test_per_node_budget_exhausted_returns_empty():
    budget = SearchBudget(total=10, per_node=1, current_node="macro")
    tool = make_web_search_tool(budget)
    budget.per_node_used["macro"] = 1
    result = tool.invoke({"query": "anything"})
    assert result == []


def test_successful_call_returns_normalized_results():
    fake_client = MagicMock()
    fake_client.search.return_value = {
        "results": [
            {"title": "T", "url": "https://example.com", "content": "snippet"},
        ]
    }
    budget = SearchBudget(total=10, per_node=3, current_node="macro")
    with patch(
        "tradingagents.graph_sector.tools.web_search.TavilyClient",
        return_value=fake_client,
    ):
        tool = make_web_search_tool(budget)
        result = tool.invoke({"query": "AI market"})
    assert result == [{"title": "T", "url": "https://example.com", "snippet": "snippet"}]
    assert budget.total_used == 1
    assert budget.per_node_used["macro"] == 1
```

- [ ] **Step 3: 실패 확인**

```bash
uv run pytest tests/graph_sector/test_web_search_tool.py -v
```

Expected: FAIL.

- [ ] **Step 4: `tradingagents/graph_sector/tools/web_search.py` 작성**

```python
"""Web search tool for sector graph nodes with budget guards.

Wraps the Tavily API in a langchain ``@tool`` callable. Each invocation is
checked against (1) a per-node call budget and (2) an overall graph budget;
exceeding either limit causes the tool to return an empty list rather than
hit the API. Callers feed the budget object through closure capture so the
LangGraph ReAct loop can't bypass it.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@dataclass
class SearchBudget:
    """Mutable budget counter shared by every web_search invocation in a run."""

    total: int = 12
    per_node: int = 3
    total_used: int = 0
    per_node_used: dict[str, int] = field(default_factory=dict)
    current_node: str | None = None

    def remaining(self) -> int:
        return max(0, self.total - self.total_used)

    def node_remaining(self) -> int:
        if not self.current_node:
            return self.per_node
        return max(0, self.per_node - self.per_node_used.get(self.current_node, 0))


def make_web_search_tool(budget: SearchBudget):
    """Return a langchain @tool bound to the given SearchBudget."""

    @tool
    def web_search(query: str) -> list[dict]:
        """Search the web for recent industry/market information.

        Returns a list of {title, url, snippet}. Returns an empty list when
        the search budget is exhausted, the API key is missing, or the
        underlying Tavily call fails.
        """
        if budget.total_used >= budget.total:
            logger.info("web_search: total budget exhausted (%d/%d)",
                        budget.total_used, budget.total)
            return []
        if budget.current_node and budget.per_node_used.get(budget.current_node, 0) >= budget.per_node:
            logger.info("web_search: node budget exhausted for %s",
                        budget.current_node)
            return []

        api_key = os.environ.get("TAVILY_API_KEY")
        if not api_key:
            logger.warning("web_search: TAVILY_API_KEY missing; returning []")
            return []

        try:
            from tavily import TavilyClient

            client = TavilyClient(api_key=api_key)
            raw = client.search(query, max_results=5, search_depth="advanced")
        except Exception:  # noqa: BLE001 — never let search crash the graph
            logger.exception("web_search: tavily call failed")
            return []

        budget.total_used += 1
        if budget.current_node:
            budget.per_node_used[budget.current_node] = (
                budget.per_node_used.get(budget.current_node, 0) + 1
            )

        return [
            {"title": r.get("title", ""),
             "url": r.get("url", ""),
             "snippet": r.get("content", "")}
            for r in raw.get("results", [])
        ]

    return web_search
```

- [ ] **Step 5: 테스트 통과**

```bash
uv run pytest tests/graph_sector/test_web_search_tool.py -v
```

Expected: PASS.

- [ ] **Step 6: 커밋**

```bash
git add tradingagents/graph_sector/ tests/graph_sector/
git commit -m "feat(sector): web_search tool with per-node + total budget guards"
```

---

## Task 6: `SectorState` + 그래프 헬퍼

**Files:**
- Create: `tradingagents/graph_sector/state.py`
- Test: `tests/graph_sector/test_state.py`

- [ ] **Step 1: 테스트 작성**

`tests/graph_sector/test_state.py`:

```python
from tradingagents.graph_sector.state import SectorState


def test_default_init_has_empty_companies():
    s = SectorState(sector_slug="ai", sector_name="AI", keywords=["GPU"])
    assert s.companies == []
    assert s.candidate_tickers == []
    assert s.budget.total == 12
    assert s.budget.per_node == 3


def test_override_budget_from_env(monkeypatch):
    monkeypatch.setenv("SECTOR_SEARCH_BUDGET", "20")
    monkeypatch.setenv("SECTOR_NODE_SEARCH_BUDGET", "5")
    s = SectorState.from_request(
        sector_slug="x", sector_name="X", keywords=[]
    )
    assert s.budget.total == 20
    assert s.budget.per_node == 5
```

- [ ] **Step 2: 실패 확인**

```bash
uv run pytest tests/graph_sector/test_state.py -v
```

Expected: FAIL.

- [ ] **Step 3: `tradingagents/graph_sector/state.py` 작성**

```python
"""SectorState — LangGraph state for the sector analysis graph."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Annotated, Any, Sequence

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from tradingagents.graph_sector.tools.web_search import SearchBudget


@dataclass
class SectorState:
    sector_slug: str
    sector_name: str
    keywords: list[str]
    messages: Annotated[Sequence[AnyMessage], add_messages] = field(default_factory=list)
    macro_report: str = ""
    value_chain_md: str = ""
    value_chain_mermaid: str = ""
    companies: list[dict[str, Any]] = field(default_factory=list)
    outlook_md: str = ""
    candidate_tickers: list[dict[str, Any]] = field(default_factory=list)
    budget: SearchBudget = field(default_factory=SearchBudget)

    @classmethod
    def from_request(
        cls,
        *,
        sector_slug: str,
        sector_name: str,
        keywords: list[str],
    ) -> "SectorState":
        total = int(os.environ.get("SECTOR_SEARCH_BUDGET", "12"))
        per_node = int(os.environ.get("SECTOR_NODE_SEARCH_BUDGET", "3"))
        return cls(
            sector_slug=sector_slug,
            sector_name=sector_name,
            keywords=keywords,
            budget=SearchBudget(total=total, per_node=per_node),
        )
```

- [ ] **Step 4: 테스트 통과**

```bash
uv run pytest tests/graph_sector/test_state.py -v
```

Expected: PASS.

- [ ] **Step 5: 커밋**

```bash
git add tradingagents/graph_sector/state.py tests/graph_sector/test_state.py
git commit -m "feat(sector): SectorState dataclass with env-driven budgets"
```

---

## Task 7: `macro_overview` 노드

**Files:**
- Create: `tradingagents/graph_sector/nodes/macro_overview.py`
- Test: `tests/graph_sector/test_macro_overview_node.py`

- [ ] **Step 1: 테스트 작성**

`tests/graph_sector/test_macro_overview_node.py`:

```python
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

from tradingagents.graph_sector.nodes.macro_overview import make_macro_overview_node
from tradingagents.graph_sector.state import SectorState


def test_macro_overview_writes_report_md():
    llm = MagicMock()
    llm.bind_tools.return_value = llm
    llm.invoke.return_value = AIMessage(content="# Macro\n시장 규모 X조원")

    node = make_macro_overview_node(llm, budget=None)
    state = SectorState(sector_slug="ai", sector_name="AI", keywords=["GPU"])
    result = node(state)
    assert "macro_report" in result
    assert "시장 규모" in result["macro_report"]
```

- [ ] **Step 2: 실패 확인**

```bash
uv run pytest tests/graph_sector/test_macro_overview_node.py -v
```

Expected: FAIL.

- [ ] **Step 3: 노드 구현**

`tradingagents/graph_sector/nodes/macro_overview.py`:

```python
"""Macro Overview node — first stage of the sector graph.

Produces a free-text Markdown report covering market size, growth, regulation,
and geopolitical context. May call ``web_search`` up to the per-node budget.
"""
from __future__ import annotations

from typing import Any, Callable

from langchain_core.messages import HumanMessage, SystemMessage

from tradingagents.graph_sector.state import SectorState
from tradingagents.graph_sector.tools.web_search import SearchBudget, make_web_search_tool


SYSTEM_PROMPT = """당신은 산업 분석가다. 주어진 산업의 **거시 환경**을 한국어 Markdown 보고서로 작성한다.
다음 항목을 반드시 포함하라:

1. 시장 규모 (USD 기준, 출처 명시)
2. 향후 3년 CAGR 추정
3. 핵심 드라이버 3–5개
4. 정책·규제·지정학 요인

근거가 약한 수치는 반드시 "(추정)" 또는 "(2024년 기준)"처럼 출처·시점을 병기하라.
필요하면 `web_search` 도구를 호출해 근거를 보강하라. 도구가 빈 결과를 돌려주면 기존 지식으로만 마무리하라.
"""


def make_macro_overview_node(llm, budget: SearchBudget | None) -> Callable:
    def node(state: SectorState) -> dict[str, Any]:
        if budget is not None:
            budget.current_node = "macro_overview"
            tools = [make_web_search_tool(budget)]
            chat = llm.bind_tools(tools)
        else:
            chat = llm

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=(
                f"산업: {state.sector_name}\n"
                f"검색 키워드 후보: {', '.join(state.keywords) or '(없음)'}"
            )),
        ]
        ai = chat.invoke(messages)
        content = ai.content if isinstance(ai.content, str) else str(ai.content)
        return {
            "macro_report": content,
            "messages": [ai],
        }

    return node
```

- [ ] **Step 4: 테스트 통과**

```bash
uv run pytest tests/graph_sector/test_macro_overview_node.py -v
```

Expected: PASS.

- [ ] **Step 5: 커밋**

```bash
git add tradingagents/graph_sector/nodes/macro_overview.py tests/graph_sector/test_macro_overview_node.py
git commit -m "feat(sector): macro_overview node with bind_tools(web_search)"
```

---

## Task 8: `value_chain` 노드 (JSON 강제 + mermaid)

**Files:**
- Create: `tradingagents/graph_sector/nodes/value_chain.py`
- Test: `tests/graph_sector/test_value_chain_node.py`

- [ ] **Step 1: 테스트 작성**

`tests/graph_sector/test_value_chain_node.py`:

```python
import json
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

from tradingagents.graph_sector.nodes.value_chain import make_value_chain_node
from tradingagents.graph_sector.state import SectorState


_VALID = {
    "stages": [
        {"name": "Upstream", "description": "소재·장비",
         "key_companies": ["ASML", "Applied Materials"]},
        {"name": "Midstream", "description": "파운드리",
         "key_companies": ["TSMC"]},
        {"name": "Downstream", "description": "팹리스/IDM",
         "key_companies": ["NVIDIA", "AMD"]},
    ],
    "mermaid": "graph LR\n  U[Upstream] --> M[Midstream] --> D[Downstream]"
}


def test_value_chain_parses_json_and_populates_fields():
    llm = MagicMock()
    llm.bind_tools.return_value = llm
    llm.invoke.return_value = AIMessage(content=json.dumps(_VALID))

    node = make_value_chain_node(llm, budget=None)
    state = SectorState(sector_slug="x", sector_name="X", keywords=[])
    result = node(state)
    assert result["value_chain_mermaid"].startswith("graph LR")
    assert "Upstream" in result["value_chain_md"]


def test_value_chain_retries_on_invalid_json():
    llm = MagicMock()
    llm.bind_tools.return_value = llm
    llm.invoke.side_effect = [
        AIMessage(content="not json at all"),
        AIMessage(content=json.dumps(_VALID)),
    ]
    node = make_value_chain_node(llm, budget=None)
    result = node(SectorState(sector_slug="x", sector_name="X", keywords=[]))
    assert llm.invoke.call_count == 2
    assert "Upstream" in result["value_chain_md"]


def test_value_chain_fallback_when_retry_fails():
    llm = MagicMock()
    llm.bind_tools.return_value = llm
    llm.invoke.return_value = AIMessage(content="garbage")
    node = make_value_chain_node(llm, budget=None)
    result = node(SectorState(sector_slug="x", sector_name="X", keywords=[]))
    # 폴백: 빈 mermaid, value_chain_md는 garbage 텍스트 보존
    assert result["value_chain_mermaid"] == ""
    assert "garbage" in result["value_chain_md"]
```

- [ ] **Step 2: 실패 확인**

```bash
uv run pytest tests/graph_sector/test_value_chain_node.py -v
```

Expected: FAIL.

- [ ] **Step 3: 노드 구현**

`tradingagents/graph_sector/nodes/value_chain.py`:

```python
"""Value-Chain node — second stage. Forces JSON output with mermaid string."""
from __future__ import annotations

import json
import logging
from typing import Any, Callable

from langchain_core.messages import HumanMessage, SystemMessage

from tradingagents.graph_sector.state import SectorState
from tradingagents.graph_sector.tools.web_search import SearchBudget, make_web_search_tool

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """당신은 산업 분석가다. 주어진 산업의 **가치사슬(Value Chain)**을 분해한다.

반드시 다음 형식의 JSON만 출력하라(마크다운 코드블록 없이 순수 JSON):

{
  "stages": [
    {"name": "Upstream — 소재/장비", "description": "...", "key_companies": ["..."]},
    {"name": "Midstream — 제조", "description": "...", "key_companies": ["..."]},
    {"name": "Downstream — 최종 제품/서비스", "description": "...", "key_companies": ["..."]}
  ],
  "mermaid": "graph LR\\n  U[Upstream] --> M[Midstream] --> D[Downstream]"
}

stages는 3–6개. mermaid 구문은 `graph LR` 또는 `flowchart LR`로 시작해야 한다.
필요하면 `web_search`로 보강하라."""


def _try_parse(content: str) -> dict | None:
    """Parse JSON from raw text, tolerating ```json fences."""
    s = content.strip()
    if s.startswith("```"):
        # strip first fence line + trailing ```
        s = "\n".join(line for line in s.splitlines() if not line.startswith("```"))
    try:
        data = json.loads(s)
        if "stages" in data and "mermaid" in data:
            return data
    except json.JSONDecodeError:
        return None
    return None


def _render_md(stages: list[dict]) -> str:
    lines = ["## 가치사슬 단계별 분해"]
    for stage in stages:
        lines.append(f"\n### {stage.get('name', '?')}")
        if desc := stage.get("description"):
            lines.append(desc)
        if companies := stage.get("key_companies"):
            lines.append("\n**주요 기업:** " + ", ".join(companies))
    return "\n".join(lines)


def make_value_chain_node(llm, budget: SearchBudget | None) -> Callable:
    def node(state: SectorState) -> dict[str, Any]:
        if budget is not None:
            budget.current_node = "value_chain"
            chat = llm.bind_tools([make_web_search_tool(budget)])
        else:
            chat = llm

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=(
                f"산업: {state.sector_name}\n"
                f"키워드: {', '.join(state.keywords)}\n\n"
                f"거시 컨텍스트:\n{state.macro_report[:2000]}"
            )),
        ]
        ai = chat.invoke(messages)
        raw = ai.content if isinstance(ai.content, str) else str(ai.content)
        parsed = _try_parse(raw)
        if parsed is None:
            # 재시도: temperature를 강제로 낮춰 다시 호출
            retry_msgs = messages + [
                ai,
                HumanMessage(content="이전 응답이 유효한 JSON이 아니다. JSON만 다시 출력하라."),
            ]
            ai = chat.invoke(retry_msgs)
            raw = ai.content if isinstance(ai.content, str) else str(ai.content)
            parsed = _try_parse(raw)

        if parsed is None:
            logger.warning("value_chain: JSON parse failed twice; falling back to raw text")
            return {
                "value_chain_md": raw,
                "value_chain_mermaid": "",
                "messages": [ai],
            }

        return {
            "value_chain_md": _render_md(parsed["stages"]),
            "value_chain_mermaid": parsed["mermaid"],
            "messages": [ai],
        }

    return node
```

- [ ] **Step 4: 테스트 통과**

```bash
uv run pytest tests/graph_sector/test_value_chain_node.py -v
```

Expected: PASS.

- [ ] **Step 5: 커밋**

```bash
git add tradingagents/graph_sector/nodes/value_chain.py tests/graph_sector/test_value_chain_node.py
git commit -m "feat(sector): value_chain node with JSON schema retry + mermaid"
```

---

## Task 9: `competitive_landscape` 노드 (companies JSON)

**Files:**
- Create: `tradingagents/graph_sector/nodes/competitive_landscape.py`
- Test: `tests/graph_sector/test_competitive_node.py`

- [ ] **Step 1: 테스트 작성**

`tests/graph_sector/test_competitive_node.py`:

```python
import json
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

from tradingagents.graph_sector.nodes.competitive_landscape import (
    make_competitive_node,
)
from tradingagents.graph_sector.state import SectorState


_VALID = {
    "companies": [
        {
            "name": "ASML", "ticker": "ASML", "stage": "Upstream — 노광장비",
            "share_value": 65.0, "share_basis": "reported",
            "confidence": "high", "sources": ["https://example.com/1"]
        },
        {
            "name": "Applied Materials", "ticker": "AMAT",
            "stage": "Upstream — 식각/증착",
            "share_value": 18.0, "share_basis": "estimated",
            "confidence": "medium", "sources": []
        },
    ]
}


def test_companies_parsed():
    llm = MagicMock()
    llm.bind_tools.return_value = llm
    llm.invoke.return_value = AIMessage(content=json.dumps(_VALID))
    node = make_competitive_node(llm, budget=None)
    state = SectorState(sector_slug="x", sector_name="X", keywords=[])
    result = node(state)
    assert len(result["companies"]) == 2
    assert result["companies"][0]["share_basis"] == "reported"


def test_unknown_basis_fallback():
    bad = {"companies": [{"name": "X", "stage": "?", "share_value": 10.0,
                          "share_basis": "totally_wrong",
                          "confidence": "high", "sources": []}]}
    llm = MagicMock()
    llm.bind_tools.return_value = llm
    llm.invoke.return_value = AIMessage(content=json.dumps(bad))
    node = make_competitive_node(llm, budget=None)
    result = node(SectorState(sector_slug="x", sector_name="X", keywords=[]))
    assert result["companies"][0]["share_basis"] == "unknown"
```

- [ ] **Step 2: 실패 확인**

```bash
uv run pytest tests/graph_sector/test_competitive_node.py -v
```

Expected: FAIL.

- [ ] **Step 3: 구현**

`tradingagents/graph_sector/nodes/competitive_landscape.py`:

```python
"""Competitive Landscape node — third stage.

Produces a list of companies with structured share/basis/confidence/sources.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable

from langchain_core.messages import HumanMessage, SystemMessage

from tradingagents.graph_sector.state import SectorState
from tradingagents.graph_sector.tools.web_search import SearchBudget, make_web_search_tool

logger = logging.getLogger(__name__)

VALID_BASIS = {"reported", "estimated", "unknown"}
VALID_CONFIDENCE = {"high", "medium", "low"}


SYSTEM_PROMPT = """당신은 산업 분석가다. 주어진 가치사슬 단계별로 **핵심 기업과 점유율**을 정리한다.

각 기업은 다음 JSON 형태로 출력:

{
  "companies": [
    {
      "name": "기업명",
      "ticker": "선택, 모르면 null",
      "stage": "가치사슬 어디 단계인지",
      "share_value": 35.0,
      "share_basis": "reported|estimated|unknown",
      "confidence": "high|medium|low",
      "sources": ["https://..."]
    }
  ]
}

규칙:
- share_basis="reported"는 출처가 명시된 보고서 수치일 때만. 추정이면 "estimated", 근거 없으면 "unknown".
- 점유율 근거 URL은 sources에 반드시 첨부.
- 단계별로 상위 3–5개 기업, 전체 10개 이하.

코드블록 없이 순수 JSON만 출력하라.
"""


def _normalize_company(c: dict) -> dict:
    basis = c.get("share_basis", "unknown")
    if basis not in VALID_BASIS:
        basis = "unknown"
    confidence = c.get("confidence", "low")
    if confidence not in VALID_CONFIDENCE:
        confidence = "low"
    return {
        "name": str(c.get("name", "Unknown")),
        "ticker": c.get("ticker"),
        "stage": str(c.get("stage", "")),
        "share_value": float(c.get("share_value", 0.0)),
        "share_basis": basis,
        "confidence": confidence,
        "sources": [str(u) for u in c.get("sources", []) if u],
    }


def _try_parse(content: str) -> list[dict] | None:
    s = content.strip()
    if s.startswith("```"):
        s = "\n".join(line for line in s.splitlines() if not line.startswith("```"))
    try:
        data = json.loads(s)
        if isinstance(data, dict) and isinstance(data.get("companies"), list):
            return [_normalize_company(c) for c in data["companies"]]
    except json.JSONDecodeError:
        return None
    return None


def make_competitive_node(llm, budget: SearchBudget | None) -> Callable:
    def node(state: SectorState) -> dict[str, Any]:
        if budget is not None:
            budget.current_node = "competitive_landscape"
            chat = llm.bind_tools([make_web_search_tool(budget)])
        else:
            chat = llm

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=(
                f"산업: {state.sector_name}\n\n"
                f"가치사슬:\n{state.value_chain_md[:3000]}"
            )),
        ]
        ai = chat.invoke(messages)
        raw = ai.content if isinstance(ai.content, str) else str(ai.content)
        parsed = _try_parse(raw)
        if parsed is None:
            retry_msgs = messages + [
                ai,
                HumanMessage(content="이전 응답이 유효한 JSON이 아니다. JSON만 다시 출력하라."),
            ]
            ai = chat.invoke(retry_msgs)
            raw = ai.content if isinstance(ai.content, str) else str(ai.content)
            parsed = _try_parse(raw)

        if parsed is None:
            logger.warning("competitive: JSON parse failed twice")
            return {"companies": [], "messages": [ai]}

        return {"companies": parsed, "messages": [ai]}

    return node
```

- [ ] **Step 4: 테스트 통과**

```bash
uv run pytest tests/graph_sector/test_competitive_node.py -v
```

Expected: PASS.

- [ ] **Step 5: 커밋**

```bash
git add tradingagents/graph_sector/nodes/competitive_landscape.py tests/graph_sector/test_competitive_node.py
git commit -m "feat(sector): competitive_landscape node with basis/confidence normalization"
```

---

## Task 10: `investment_outlook` 노드 (candidate_tickers)

**Files:**
- Create: `tradingagents/graph_sector/nodes/investment_outlook.py`
- Test: `tests/graph_sector/test_outlook_node.py`

- [ ] **Step 1: 테스트 작성**

`tests/graph_sector/test_outlook_node.py`:

```python
import json
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

from tradingagents.graph_sector.nodes.investment_outlook import (
    make_investment_outlook_node,
)
from tradingagents.graph_sector.state import SectorState


_VALID = {
    "summary_md": "## 전망\n수혜: ...\n리스크: ...",
    "candidate_tickers": [
        {"ticker": "NVDA", "name": "NVIDIA", "stage": "Downstream", "reason": "AI accelerator leader"},
        {"ticker": "TSM", "name": "TSMC", "stage": "Midstream", "reason": "foundry"},
    ]
}


def test_outlook_fields_populated():
    llm = MagicMock()
    llm.invoke.return_value = AIMessage(content=json.dumps(_VALID))
    node = make_investment_outlook_node(llm)
    state = SectorState(sector_slug="x", sector_name="X", keywords=[])
    state.companies = [{"name": "NVIDIA", "ticker": "NVDA", "stage": "Downstream",
                        "share_value": 80, "share_basis": "reported",
                        "confidence": "high", "sources": []}]
    result = node(state)
    assert "수혜" in result["outlook_md"]
    assert len(result["candidate_tickers"]) == 2
    assert result["candidate_tickers"][0]["ticker"] == "NVDA"


def test_outlook_fallback_on_invalid_json():
    llm = MagicMock()
    llm.invoke.return_value = AIMessage(content="not json")
    node = make_investment_outlook_node(llm)
    result = node(SectorState(sector_slug="x", sector_name="X", keywords=[]))
    assert result["candidate_tickers"] == []
    assert result["outlook_md"] == "not json"
```

- [ ] **Step 2: 실패 확인**

```bash
uv run pytest tests/graph_sector/test_outlook_node.py -v
```

Expected: FAIL.

- [ ] **Step 3: 구현**

`tradingagents/graph_sector/nodes/investment_outlook.py`:

```python
"""Investment Outlook node — final stage.

Synthesizes prior stage outputs into an investment outlook + candidate ticker
list. No web_search at this stage — purely synthesis.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable

from langchain_core.messages import HumanMessage, SystemMessage

from tradingagents.graph_sector.state import SectorState

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """당신은 산업 분석가다. 주어진 컨텍스트를 종합해 **투자 전망**과 **후보 종목**을 정리한다.

다음 JSON만 출력하라(코드블록 없이):

{
  "summary_md": "## 수혜\\n...\\n## 리스크\\n...",
  "candidate_tickers": [
    {"ticker": "AAPL", "name": "Apple", "stage": "Downstream — 디바이스", "reason": "..."}
  ]
}

candidate_tickers는 5–10개. 한국·미국·기타 시장을 균형 있게 포함하라.
reason은 가치사슬 어느 단계에서 어떤 이유로 수혜인지 한 문장."""


def _try_parse(content: str) -> dict | None:
    s = content.strip()
    if s.startswith("```"):
        s = "\n".join(line for line in s.splitlines() if not line.startswith("```"))
    try:
        data = json.loads(s)
        if isinstance(data, dict) and "summary_md" in data and "candidate_tickers" in data:
            return data
    except json.JSONDecodeError:
        return None
    return None


def make_investment_outlook_node(llm) -> Callable:
    def node(state: SectorState) -> dict[str, Any]:
        companies_brief = "\n".join(
            f"- {c['name']} ({c.get('ticker', '?')}): {c['stage']} {c['share_value']}% ({c['share_basis']})"
            for c in state.companies[:20]
        )
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=(
                f"산업: {state.sector_name}\n\n"
                f"거시:\n{state.macro_report[:1500]}\n\n"
                f"가치사슬:\n{state.value_chain_md[:1500]}\n\n"
                f"경쟁사:\n{companies_brief}"
            )),
        ]
        ai = llm.invoke(messages)
        raw = ai.content if isinstance(ai.content, str) else str(ai.content)
        parsed = _try_parse(raw)
        if parsed is None:
            retry_msgs = messages + [
                ai,
                HumanMessage(content="JSON만 다시 출력하라."),
            ]
            ai = llm.invoke(retry_msgs)
            raw = ai.content if isinstance(ai.content, str) else str(ai.content)
            parsed = _try_parse(raw)

        if parsed is None:
            logger.warning("outlook: JSON parse failed twice")
            return {
                "outlook_md": raw,
                "candidate_tickers": [],
                "messages": [ai],
            }

        candidates = [
            {
                "ticker": str(c.get("ticker", "")),
                "name": str(c.get("name", "")),
                "stage": str(c.get("stage", "")),
                "reason": str(c.get("reason", "")),
            }
            for c in parsed.get("candidate_tickers", [])
            if c.get("ticker")
        ]
        return {
            "outlook_md": parsed.get("summary_md", ""),
            "candidate_tickers": candidates,
            "messages": [ai],
        }

    return node
```

- [ ] **Step 4: 테스트 통과**

```bash
uv run pytest tests/graph_sector/test_outlook_node.py -v
```

Expected: PASS.

- [ ] **Step 5: 커밋**

```bash
git add tradingagents/graph_sector/nodes/investment_outlook.py tests/graph_sector/test_outlook_node.py
git commit -m "feat(sector): investment_outlook node — synthesis + candidate tickers"
```

---

## Task 11: `sector_graph` 빌더

**Files:**
- Create: `tradingagents/graph_sector/sector_graph.py`
- Test: `tests/graph_sector/test_sector_graph.py`

- [ ] **Step 1: 테스트 작성**

`tests/graph_sector/test_sector_graph.py`:

```python
import json
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

from tradingagents.graph_sector.sector_graph import build_sector_graph
from tradingagents.graph_sector.state import SectorState


def test_graph_runs_all_four_phases():
    deep = MagicMock()
    deep.bind_tools.return_value = deep
    deep.invoke.side_effect = [
        AIMessage(content="# Macro"),  # macro
        AIMessage(content=json.dumps({  # value_chain
            "stages": [{"name": "U", "description": "", "key_companies": []}],
            "mermaid": "graph LR\n  U[U]"
        })),
        AIMessage(content=json.dumps({  # competitive
            "companies": [
                {"name": "X", "stage": "U", "share_value": 50.0,
                 "share_basis": "reported", "confidence": "high", "sources": []}
            ]
        })),
        AIMessage(content=json.dumps({  # outlook
            "summary_md": "## OK",
            "candidate_tickers": [
                {"ticker": "X", "name": "X", "stage": "U", "reason": "lead"}
            ]
        })),
    ]
    graph = build_sector_graph(quick_llm=deep, deep_llm=deep)
    state = SectorState.from_request(
        sector_slug="ai", sector_name="AI", keywords=["GPU"]
    )
    final = graph.invoke(state)
    assert final["macro_report"].startswith("# Macro")
    assert final["value_chain_mermaid"].startswith("graph LR")
    assert len(final["companies"]) == 1
    assert final["candidate_tickers"][0]["ticker"] == "X"
```

- [ ] **Step 2: 실패 확인**

```bash
uv run pytest tests/graph_sector/test_sector_graph.py -v
```

Expected: FAIL.

- [ ] **Step 3: 그래프 빌더 작성**

`tradingagents/graph_sector/sector_graph.py`:

```python
"""LangGraph builder for the 4-stage sector analysis graph."""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from tradingagents.graph_sector.nodes.competitive_landscape import (
    make_competitive_node,
)
from tradingagents.graph_sector.nodes.investment_outlook import (
    make_investment_outlook_node,
)
from tradingagents.graph_sector.nodes.macro_overview import make_macro_overview_node
from tradingagents.graph_sector.nodes.value_chain import make_value_chain_node
from tradingagents.graph_sector.state import SectorState
from tradingagents.graph_sector.tools.web_search import SearchBudget


def build_sector_graph(*, quick_llm, deep_llm, budget: SearchBudget | None = None):
    """Compile a sequential 4-stage StateGraph.

    Macro → ValueChain → Competitive → Outlook → END.
    A shared SearchBudget tracks per-node and total web_search calls.
    """
    g = StateGraph(SectorState)
    g.add_node("macro_overview", make_macro_overview_node(deep_llm, budget))
    g.add_node("value_chain", make_value_chain_node(deep_llm, budget))
    g.add_node("competitive_landscape", make_competitive_node(deep_llm, budget))
    g.add_node("investment_outlook", make_investment_outlook_node(deep_llm))

    g.set_entry_point("macro_overview")
    g.add_edge("macro_overview", "value_chain")
    g.add_edge("value_chain", "competitive_landscape")
    g.add_edge("competitive_landscape", "investment_outlook")
    g.add_edge("investment_outlook", END)
    return g.compile()
```

- [ ] **Step 4: 테스트 통과**

```bash
uv run pytest tests/graph_sector/test_sector_graph.py -v
```

Expected: PASS.

- [ ] **Step 5: 커밋**

```bash
git add tradingagents/graph_sector/sector_graph.py tests/graph_sector/test_sector_graph.py
git commit -m "feat(sector): sector_graph builder with sequential 4-stage flow"
```

---

## Task 12: `FakeSectorRunner` (LLM 없이 흐름 검증)

**Files:**
- Create: `tradingagents_web/services/sector_fake_runner.py`
- Test: `tests/web/test_sector_fake_runner.py`

- [ ] **Step 1: 테스트 작성**

`tests/web/test_sector_fake_runner.py`:

```python
import asyncio
from datetime import datetime, timezone

import pytest

from tradingagents_web.services.event_bus import EventBus
from tradingagents_web.services.sector_fake_runner import (
    FakeSectorRunner,
    SectorRunRequest,
)


@pytest.mark.asyncio
async def test_fake_runner_emits_four_phases():
    bus = EventBus()
    runner = FakeSectorRunner(bus)
    events: list[dict] = []

    async def collect():
        async for ev in bus.subscribe(run_id="r1"):
            events.append({"type": ev.type, "phase": ev.payload.get("phase")})
            if ev.type in ("completed", "error"):
                break

    request = SectorRunRequest(
        run_id="r1", sector_id=1, sector_slug="ai",
        sector_name="AI", keywords=[],
        analysis_date=datetime.now(timezone.utc).date(),
    )
    task = asyncio.create_task(collect())
    await runner.run(request)
    await asyncio.wait_for(task, timeout=3.0)

    phases = [e["phase"] for e in events if e["type"] == "progress"]
    assert phases == ["macro", "value_chain", "competitive", "outlook"]
    assert events[-1]["type"] == "completed"
```

- [ ] **Step 2: 실패 확인**

```bash
uv run pytest tests/web/test_sector_fake_runner.py -v
```

Expected: FAIL.

- [ ] **Step 3: 구현**

`tradingagents_web/services/sector_fake_runner.py`:

```python
"""Fake sector runner — for WEB_FAKE_RUNNER=true UI / E2E / SSE testing."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from tradingagents_web.services.event_bus import AnalysisEvent, EventBus


SECTOR_PHASE_ORDER: tuple[str, ...] = ("macro", "value_chain", "competitive", "outlook")
SECTOR_PHASE_LABELS: dict[str, str] = {
    "macro": "거시 환경",
    "value_chain": "가치사슬",
    "competitive": "경쟁 구도",
    "outlook": "투자 전망",
}


@dataclass
class SectorRunRequest:
    run_id: str
    sector_id: int
    sector_slug: str
    sector_name: str
    keywords: list[str]
    analysis_date: date
    llm_quick_model: str | None = None
    llm_deep_model: str | None = None


@dataclass
class SectorRunResult:
    report_md: str
    value_chain_mermaid: str
    companies: list[dict] = field(default_factory=list)
    outlook_summary: str = ""
    candidate_tickers: list[dict] = field(default_factory=list)
    search_call_count: int = 0


def _progress(phase: str) -> dict:
    return {
        "step": SECTOR_PHASE_ORDER.index(phase) + 1,
        "total": len(SECTOR_PHASE_ORDER),
        "phase": phase,
        "phase_label": SECTOR_PHASE_LABELS[phase],
    }


_DUMMY_MERMAID = """graph LR
  U[Upstream — 소재/장비] --> M[Midstream — 제조]
  M --> D[Downstream — 최종 제품]
"""

_DUMMY_COMPANIES = [
    {"name": "ASML", "ticker": "ASML", "stage": "Upstream — EUV 노광장비",
     "share_value": 65.0, "share_basis": "reported", "confidence": "high",
     "sources": ["https://www.asml.com/en/investors"]},
    {"name": "TSMC", "ticker": "TSM", "stage": "Midstream — 파운드리",
     "share_value": 55.0, "share_basis": "reported", "confidence": "high",
     "sources": ["https://example.com/tsm"]},
]

_DUMMY_CANDIDATES = [
    {"ticker": "NVDA", "name": "NVIDIA", "stage": "Downstream — AI 가속기",
     "reason": "AI 가속기 시장 점유율 80% 이상"},
    {"ticker": "TSM", "name": "TSMC", "stage": "Midstream — 파운드리",
     "reason": "선단공정 사실상 독점"},
]


class FakeSectorRunner:
    def __init__(self, bus: EventBus) -> None:
        self.bus = bus

    async def run(self, request: SectorRunRequest) -> SectorRunResult:
        for phase in SECTOR_PHASE_ORDER:
            await self.bus.publish(AnalysisEvent(
                run_id=request.run_id,
                type="progress",
                payload=_progress(phase),
                timestamp=datetime.now(timezone.utc),
            ))
            await asyncio.sleep(0.05)

        result = SectorRunResult(
            report_md=(
                f"# {request.sector_name} 산업 분석\n\n"
                "(WEB_FAKE_RUNNER=true 모드의 더미 리포트)\n"
            ),
            value_chain_mermaid=_DUMMY_MERMAID,
            companies=_DUMMY_COMPANIES,
            outlook_summary="## 수혜\n선단공정 의존도 ↑.\n## 리스크\n중국 규제 변동.",
            candidate_tickers=_DUMMY_CANDIDATES,
            search_call_count=0,
        )
        await self.bus.publish(AnalysisEvent(
            run_id=request.run_id,
            type="completed",
            payload={"sector_id": request.sector_id},
            timestamp=datetime.now(timezone.utc),
        ))
        return result
```

- [ ] **Step 4: 테스트 통과**

```bash
uv run pytest tests/web/test_sector_fake_runner.py -v
```

Expected: PASS.

- [ ] **Step 5: 커밋**

```bash
git add tradingagents_web/services/sector_fake_runner.py tests/web/test_sector_fake_runner.py
git commit -m "feat(sector): FakeSectorRunner for fake-runner mode + E2E"
```

---

## Task 13: `RealSectorRunner` (LangGraph 통합)

**Files:**
- Create: `tradingagents_web/services/sector_runner.py`
- Test: `tests/web/test_sector_runner.py`

- [ ] **Step 1: 테스트 작성**

`tests/web/test_sector_runner.py`:

```python
import asyncio
import json
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from tradingagents_web.services.event_bus import EventBus
from tradingagents_web.services.sector_runner import RealSectorRunner
from tradingagents_web.services.sector_fake_runner import SectorRunRequest


@pytest.mark.asyncio
async def test_real_runner_progresses_through_phases():
    bus = EventBus()
    events: list[str] = []

    async def collect():
        async for ev in bus.subscribe(run_id="r1"):
            events.append(ev.payload.get("phase") or ev.type)
            if ev.type in ("completed", "error"):
                break

    deep = MagicMock()
    deep.bind_tools.return_value = deep
    deep.invoke.side_effect = [
        AIMessage(content="# Macro"),
        AIMessage(content=json.dumps({
            "stages": [{"name": "U", "description": "", "key_companies": []}],
            "mermaid": "graph LR\n  U[U]"
        })),
        AIMessage(content=json.dumps({
            "companies": [{"name": "X", "stage": "U", "share_value": 10.0,
                          "share_basis": "estimated", "confidence": "medium",
                          "sources": []}]
        })),
        AIMessage(content=json.dumps({
            "summary_md": "## OK",
            "candidate_tickers": [{"ticker": "X", "name": "X",
                                   "stage": "U", "reason": "..."}]
        })),
    ]

    runner = RealSectorRunner(bus, llm_factory=lambda model: deep)
    request = SectorRunRequest(
        run_id="r1", sector_id=1, sector_slug="ai",
        sector_name="AI", keywords=[],
        analysis_date=date(2026, 5, 28),
    )
    task = asyncio.create_task(collect())
    result = await runner.run(request)
    await asyncio.wait_for(task, timeout=5.0)

    # 4단계 phase + completed
    assert "macro" in events
    assert "value_chain" in events
    assert "competitive" in events
    assert "outlook" in events
    assert events[-1] == "completed"
    assert len(result.companies) == 1
    assert result.candidate_tickers[0]["ticker"] == "X"
```

- [ ] **Step 2: 실패 확인**

```bash
uv run pytest tests/web/test_sector_runner.py -v
```

Expected: FAIL.

- [ ] **Step 3: 구현**

`tradingagents_web/services/sector_runner.py`:

```python
"""Real sector runner — drives the sector LangGraph and emits phase progress.

Mirrors tradingagents_web.services.runner.RealRunner but for the
``graph_sector`` package. Phase mapping collapses LangGraph node names to four
user-facing phases (macro / value_chain / competitive / outlook).
"""
from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Awaitable, Callable

from tradingagents.graph_sector.sector_graph import build_sector_graph
from tradingagents.graph_sector.state import SectorState
from tradingagents.graph_sector.tools.web_search import SearchBudget
from tradingagents_web.services.event_bus import AnalysisEvent, EventBus
from tradingagents_web.services.sector_fake_runner import (
    SECTOR_PHASE_LABELS,
    SECTOR_PHASE_ORDER,
    SectorRunRequest,
    SectorRunResult,
)

logger = logging.getLogger(__name__)

LLMFactory = Callable[[str | None], object]

_NODE_TO_PHASE: dict[str, str] = {
    "macro_overview": "macro",
    "value_chain": "value_chain",
    "competitive_landscape": "competitive",
    "investment_outlook": "outlook",
}


def _progress(phase: str) -> dict:
    return {
        "step": SECTOR_PHASE_ORDER.index(phase) + 1,
        "total": len(SECTOR_PHASE_ORDER),
        "phase": phase,
        "phase_label": SECTOR_PHASE_LABELS[phase],
    }


class RealSectorRunner:
    """Drives the sector LangGraph and emits AnalysisEvents on phase changes."""

    def __init__(self, bus: EventBus, *, llm_factory: LLMFactory) -> None:
        self.bus = bus
        self.llm_factory = llm_factory

    async def run(self, request: SectorRunRequest) -> SectorRunResult:
        deep_llm = self.llm_factory(request.llm_deep_model)
        quick_llm = self.llm_factory(request.llm_quick_model)
        budget = SearchBudget()
        graph = build_sector_graph(
            quick_llm=quick_llm, deep_llm=deep_llm, budget=budget,
        )
        state = SectorState.from_request(
            sector_slug=request.sector_slug,
            sector_name=request.sector_name,
            keywords=request.keywords,
        )

        seen_phases: set[str] = set()
        final_state: dict | None = None

        try:
            async for chunk in graph.astream(state):
                # chunk format: {node_name: state_partial}
                for node_name, partial in chunk.items():
                    phase = _NODE_TO_PHASE.get(node_name)
                    if phase and phase not in seen_phases:
                        seen_phases.add(phase)
                        await self.bus.publish(AnalysisEvent(
                            run_id=request.run_id,
                            type="progress",
                            payload=_progress(phase),
                            timestamp=datetime.now(timezone.utc),
                        ))
                    final_state = {**(final_state or {}), **partial}
        except Exception as exc:
            logger.exception("sector_runner: graph failed")
            await self.bus.publish(AnalysisEvent(
                run_id=request.run_id,
                type="error",
                payload={"message": str(exc)},
                timestamp=datetime.now(timezone.utc),
            ))
            raise

        if final_state is None:
            raise RuntimeError("graph produced no state")

        report_md = self._compose_report_md(request.sector_name, final_state)
        result = SectorRunResult(
            report_md=report_md,
            value_chain_mermaid=final_state.get("value_chain_mermaid", ""),
            companies=final_state.get("companies", []),
            outlook_summary=final_state.get("outlook_md", ""),
            candidate_tickers=final_state.get("candidate_tickers", []),
            search_call_count=budget.total_used,
        )
        await self.bus.publish(AnalysisEvent(
            run_id=request.run_id,
            type="completed",
            payload={"sector_id": request.sector_id},
            timestamp=datetime.now(timezone.utc),
        ))
        return result

    @staticmethod
    def _compose_report_md(sector_name: str, state: dict) -> str:
        parts = [
            f"# {sector_name} 산업 분석\n",
            "## 거시 환경", state.get("macro_report", ""),
            state.get("value_chain_md", ""),
            "## 경쟁 구도 · 핵심 기업",
            _companies_md_table(state.get("companies", [])),
            "## 투자 전망", state.get("outlook_md", ""),
        ]
        return "\n\n".join(p for p in parts if p)


def _companies_md_table(companies: list[dict]) -> str:
    if not companies:
        return "_데이터 없음_"
    rows = ["| 기업 | 단계 | 점유율 | 근거 | 신뢰도 |", "|---|---|---|---|---|"]
    for c in companies:
        rows.append(
            f"| {c['name']} ({c.get('ticker') or '-'}) | {c['stage']} "
            f"| {c['share_value']}% | {c['share_basis']} | {c['confidence']} |"
        )
    return "\n".join(rows)
```

- [ ] **Step 4: 테스트 통과**

```bash
uv run pytest tests/web/test_sector_runner.py -v
```

Expected: PASS.

- [ ] **Step 5: 커밋**

```bash
git add tradingagents_web/services/sector_runner.py tests/web/test_sector_runner.py
git commit -m "feat(sector): RealSectorRunner with phase progress + report markdown"
```

---

## Task 14: API — CRUD (`GET/POST/DELETE /api/sectors`)

**Files:**
- Create: `tradingagents_web/api/sectors.py`
- Modify: `tradingagents_web/main.py` (라우터 등록)
- Test: `tests/web/test_sectors_api.py`

- [ ] **Step 1: 테스트 작성**

`tests/web/test_sectors_api.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_list_sectors_returns_presets(authed_client):
    resp = await authed_client.get("/api/sectors")
    assert resp.status_code == 200
    slugs = {s["slug"] for s in resp.json()}
    assert "ai" in slugs and "robotics" in slugs


@pytest.mark.asyncio
async def test_create_user_sector(authed_client):
    resp = await authed_client.post("/api/sectors", json={
        "name": "양자 컴퓨팅",
        "description": "양자 컴퓨팅 산업",
        "keywords": ["IonQ", "qubits"]
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["slug"] == "양자-컴퓨팅" or body["slug"].startswith("yang") or body["slug"].endswith("ing")
    assert body["is_preset"] is False


@pytest.mark.asyncio
async def test_delete_preset_returns_409(authed_client):
    listing = (await authed_client.get("/api/sectors")).json()
    ai = next(s for s in listing if s["slug"] == "ai")
    resp = await authed_client.delete(f"/api/sectors/{ai['id']}")
    assert resp.status_code == 409
```

- [ ] **Step 2: 실패 확인**

```bash
uv run pytest tests/web/test_sectors_api.py -v
```

Expected: FAIL (라우터 미존재).

- [ ] **Step 3: API 구현 (CRUD 부분)**

`tradingagents_web/api/sectors.py`:

```python
"""/api/sectors — sector CRUD + run trigger + SSE.

Patterns mirror tradingagents_web/api/runs.py for consistency.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tradingagents_web.api.auth import require_user
from tradingagents_web.db import get_db
from tradingagents_web.models.sector import Sector
from tradingagents_web.models.sector_report import SectorReport
from tradingagents_web.schemas.sector import (
    SectorCreate,
    SectorOut,
    SectorReportOut,
    SectorReportSummary,
    SectorRunCreate,
    SectorRunOut,
)

router = APIRouter(prefix="/api/sectors", tags=["sectors"])


def _augment_out(sector: Sector, db: Session) -> SectorOut:
    latest = db.execute(
        select(SectorReport)
        .where(SectorReport.sector_id == sector.id)
        .order_by(desc(SectorReport.version))
        .limit(1)
    ).scalar_one_or_none()
    return SectorOut(
        id=sector.id,
        slug=sector.slug,
        name=sector.name,
        description=sector.description,
        keywords=sector.keywords,
        is_preset=sector.is_preset,
        created_at=sector.created_at,
        latest_report_version=latest.version if latest else None,
        latest_report_at=latest.created_at if latest else None,
    )


@router.get("", response_model=list[SectorOut])
async def list_sectors(
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_user),
):
    sectors = db.execute(select(Sector).order_by(Sector.id)).scalars().all()
    return [_augment_out(s, db) for s in sectors]


@router.post("", response_model=SectorOut, status_code=201)
async def create_sector(
    payload: SectorCreate,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_user),
):
    sector = Sector(
        slug=payload.slug,
        name=payload.name,
        description=payload.description,
        keywords=payload.keywords,
        is_preset=False,
        created_at=datetime.now(timezone.utc),
    )
    db.add(sector)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"slug '{payload.slug}' already exists",
        )
    db.refresh(sector)
    return _augment_out(sector, db)


@router.delete("/{sector_id}", status_code=204)
async def delete_sector(
    sector_id: int,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_user),
):
    sector = db.get(Sector, sector_id)
    if sector is None:
        raise HTTPException(404, "sector not found")
    if sector.is_preset:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "preset sectors cannot be deleted",
        )
    db.delete(sector)
    db.commit()
    return None
```

- [ ] **Step 4: 라우터 등록**

`tradingagents_web/main.py`에서 다른 라우터 include 옆에:

```python
from tradingagents_web.api import sectors as sectors_api
...
app.include_router(sectors_api.router)
```

- [ ] **Step 5: 테스트 통과**

```bash
uv run pytest tests/web/test_sectors_api.py -v
```

Expected: PASS (CRUD 부분).

- [ ] **Step 6: 커밋**

```bash
git add tradingagents_web/api/sectors.py tradingagents_web/main.py tests/web/test_sectors_api.py
git commit -m "feat(sector): /api/sectors CRUD endpoints with preset protection"
```

---

## Task 15: API — runs + SSE

**Files:**
- Modify: `tradingagents_web/api/sectors.py` (run 엔드포인트 추가)
- Test: `tests/web/test_sectors_api.py` (run 케이스 추가)

- [ ] **Step 1: 테스트 추가**

`tests/web/test_sectors_api.py` 끝에:

```python
import os

import pytest


@pytest.mark.asyncio
async def test_start_run_returns_run_id(authed_client, monkeypatch):
    monkeypatch.setenv("WEB_FAKE_RUNNER", "true")
    ai = next(s for s in (await authed_client.get("/api/sectors")).json()
              if s["slug"] == "ai")
    resp = await authed_client.post(f"/api/sectors/{ai['id']}/runs", json={})
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "running"
    assert body["sector_id"] == ai["id"]
    assert len(body["id"]) > 10


@pytest.mark.asyncio
async def test_duplicate_running_returns_409(authed_client, monkeypatch):
    monkeypatch.setenv("WEB_FAKE_RUNNER", "true")
    ai = next(s for s in (await authed_client.get("/api/sectors")).json()
              if s["slug"] == "ai")
    # 첫 호출
    await authed_client.post(f"/api/sectors/{ai['id']}/runs", json={})
    # 즉시 두 번째
    resp = await authed_client.post(f"/api/sectors/{ai['id']}/runs", json={})
    assert resp.status_code == 409
```

- [ ] **Step 2: 실패 확인**

```bash
uv run pytest tests/web/test_sectors_api.py -v
```

Expected: FAIL.

- [ ] **Step 3: run + SSE 엔드포인트 추가**

`tradingagents_web/api/sectors.py`에 추가:

```python
import asyncio
import os
import uuid

from fastapi import BackgroundTasks
from sse_starlette.sse import EventSourceResponse

from tradingagents_web.models.sector_run import SectorRun
from tradingagents_web.services.event_bus import EventBus, get_event_bus
from tradingagents_web.services.sector_fake_runner import (
    FakeSectorRunner,
    SectorRunRequest,
)
from tradingagents_web.services.sector_runner import RealSectorRunner


def _build_runner(bus: EventBus):
    if os.environ.get("WEB_FAKE_RUNNER", "false").lower() == "true":
        return FakeSectorRunner(bus)
    # llm_factory: 종목 runner와 동일 패턴으로 재사용 가능하면 import.
    # 여기선 placeholder. 실제 통합은 tradingagents_web/services/llm_factory.py에서 가져옴.
    from tradingagents_web.services.llm_factory import build_chat_llm
    return RealSectorRunner(bus, llm_factory=build_chat_llm)


@router.post("/{sector_id}/runs", response_model=SectorRunOut, status_code=202)
async def start_sector_run(
    sector_id: int,
    payload: SectorRunCreate,
    background: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    bus: Annotated[EventBus, Depends(get_event_bus)],
    user=Depends(require_user),
):
    sector = db.get(Sector, sector_id)
    if sector is None:
        raise HTTPException(404, "sector not found")

    running = db.execute(
        select(SectorRun)
        .where(SectorRun.sector_id == sector_id)
        .where(SectorRun.status == "running")
    ).scalar_one_or_none()
    if running is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"sector {sector.slug} already has a running analysis ({running.id})",
        )

    run = SectorRun(
        id=str(uuid.uuid4()),
        sector_id=sector_id,
        status="running",
        phase=None,
        started_at=datetime.now(timezone.utc),
        llm_quick_model=payload.llm_quick_model,
        llm_deep_model=payload.llm_deep_model,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    runner = _build_runner(bus)
    background.add_task(
        _execute_sector_run, run.id, sector_id, sector.slug, sector.name,
        sector.keywords or [], payload, bus,
    )
    return SectorRunOut.model_validate(run)


async def _execute_sector_run(
    run_id: str,
    sector_id: int,
    sector_slug: str,
    sector_name: str,
    keywords: list[str],
    payload: SectorRunCreate,
    bus: EventBus,
) -> None:
    """Background task — executes the runner and persists results."""
    from tradingagents_web.db import SessionLocal

    runner = _build_runner(bus)
    request = SectorRunRequest(
        run_id=run_id, sector_id=sector_id,
        sector_slug=sector_slug, sector_name=sector_name,
        keywords=keywords,
        analysis_date=datetime.now(timezone.utc).date(),
        llm_quick_model=payload.llm_quick_model,
        llm_deep_model=payload.llm_deep_model,
    )
    db = SessionLocal()
    try:
        result = await runner.run(request)
        run = db.get(SectorRun, run_id)
        run.status = "completed"
        run.finished_at = datetime.now(timezone.utc)
        run.phase = "outlook"
        run.search_call_count = result.search_call_count

        # 다음 version 계산
        max_version = db.execute(
            select(SectorReport.version)
            .where(SectorReport.sector_id == sector_id)
            .order_by(desc(SectorReport.version))
            .limit(1)
        ).scalar_one_or_none()
        next_version = (max_version or 0) + 1
        report = SectorReport(
            sector_id=sector_id,
            run_id=run_id,
            version=next_version,
            report_md=result.report_md,
            value_chain_mermaid=result.value_chain_mermaid,
            companies=result.companies,
            outlook_summary=result.outlook_summary,
            candidate_tickers=result.candidate_tickers,
            created_at=datetime.now(timezone.utc),
        )
        db.add(report)
        db.commit()
    except Exception as exc:
        run = db.get(SectorRun, run_id)
        if run is not None:
            run.status = "failed"
            run.error = str(exc)[:2000]
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()


@router.get("/{sector_id}/runs/{run_id}/stream")
async def stream_sector_run(
    sector_id: int,
    run_id: str,
    db: Annotated[Session, Depends(get_db)],
    bus: Annotated[EventBus, Depends(get_event_bus)],
    user=Depends(require_user),
):
    run = db.get(SectorRun, run_id)
    if run is None or run.sector_id != sector_id:
        raise HTTPException(404, "run not found")

    async def event_stream():
        async for ev in bus.subscribe(run_id=run_id):
            yield {"event": ev.type, "data": ev.json_payload()}
            if ev.type in ("completed", "error"):
                break

    return EventSourceResponse(event_stream())
```

- [ ] **Step 4: 테스트 통과**

```bash
uv run pytest tests/web/test_sectors_api.py -v
```

Expected: PASS.

- [ ] **Step 5: 커밋**

```bash
git add tradingagents_web/api/sectors.py tests/web/test_sectors_api.py
git commit -m "feat(sector): start-run + SSE stream endpoints"
```

---

## Task 16: API — reports (GET 목록 + 단일 + latest)

**Files:**
- Modify: `tradingagents_web/api/sectors.py`
- Test: `tests/web/test_sectors_api.py`

- [ ] **Step 1: 테스트 추가**

```python
@pytest.mark.asyncio
async def test_get_latest_report_404_when_no_reports(authed_client):
    ai = next(s for s in (await authed_client.get("/api/sectors")).json()
              if s["slug"] == "ai")
    resp = await authed_client.get(f"/api/sectors/{ai['id']}/reports/latest")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_reports_empty(authed_client):
    ai = next(s for s in (await authed_client.get("/api/sectors")).json()
              if s["slug"] == "ai")
    resp = await authed_client.get(f"/api/sectors/{ai['id']}/reports")
    assert resp.status_code == 200
    assert resp.json() == []
```

- [ ] **Step 2: 실패 확인**

```bash
uv run pytest tests/web/test_sectors_api.py -v -k report
```

Expected: FAIL.

- [ ] **Step 3: 엔드포인트 추가**

`tradingagents_web/api/sectors.py`에 추가:

```python
@router.get("/{sector_id}/reports", response_model=list[SectorReportSummary])
async def list_reports(
    sector_id: int,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_user),
):
    rows = db.execute(
        select(SectorReport)
        .where(SectorReport.sector_id == sector_id)
        .order_by(desc(SectorReport.version))
    ).scalars().all()
    return [SectorReportSummary.model_validate(r) for r in rows]


@router.get("/{sector_id}/reports/latest", response_model=SectorReportOut)
async def get_latest_report(
    sector_id: int,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_user),
):
    row = db.execute(
        select(SectorReport)
        .where(SectorReport.sector_id == sector_id)
        .order_by(desc(SectorReport.version))
        .limit(1)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "no reports yet")
    return SectorReportOut.model_validate(row)


@router.get("/{sector_id}/reports/{report_id}", response_model=SectorReportOut)
async def get_report(
    sector_id: int,
    report_id: int,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_user),
):
    row = db.get(SectorReport, report_id)
    if row is None or row.sector_id != sector_id:
        raise HTTPException(404, "report not found")
    return SectorReportOut.model_validate(row)
```

- [ ] **Step 4: 테스트 통과**

```bash
uv run pytest tests/web/test_sectors_api.py -v
```

Expected: PASS.

- [ ] **Step 5: 커밋**

```bash
git add tradingagents_web/api/sectors.py tests/web/test_sectors_api.py
git commit -m "feat(sector): reports list + latest + single endpoints"
```

---

## Task 17: 프런트 — 의존성 + 타입 + `/sectors` 목록

**Files:**
- Modify: `web/package.json`
- Create: `web/lib/sectors.ts`
- Create: `web/components/sector/sector-card.tsx`
- Create: `web/app/(workspace)/sectors/page.tsx`

- [ ] **Step 1: `mermaid` 추가**

`web/package.json`의 dependencies:

```json
"mermaid": "^11.4.0",
```

```bash
cd web && npm install
```

- [ ] **Step 2: 타입/페처 작성 — `web/lib/sectors.ts`**

```typescript
export type ShareBasis = "reported" | "estimated" | "unknown";
export type Confidence = "high" | "medium" | "low";

export interface SectorSummary {
  id: number;
  slug: string;
  name: string;
  description: string | null;
  keywords: string[];
  is_preset: boolean;
  created_at: string;
  latest_report_version: number | null;
  latest_report_at: string | null;
}

export interface CompanyShare {
  name: string;
  ticker: string | null;
  stage: string;
  share_value: number;
  share_basis: ShareBasis;
  confidence: Confidence;
  sources: string[];
}

export interface CandidateTicker {
  ticker: string;
  name: string;
  stage: string;
  reason: string;
}

export interface SectorReport {
  id: number;
  sector_id: number;
  run_id: string;
  version: number;
  report_md: string;
  value_chain_mermaid: string;
  companies: CompanyShare[];
  outlook_summary: string;
  candidate_tickers: CandidateTicker[];
  created_at: string;
}

export interface SectorRun {
  id: string;
  sector_id: number;
  status: "running" | "completed" | "failed";
  phase: string | null;
  started_at: string;
  finished_at: string | null;
  error: string | null;
  search_call_count: number;
}

export async function listSectors(): Promise<SectorSummary[]> {
  const r = await fetch("/api/sectors", { credentials: "include" });
  if (!r.ok) throw new Error(`listSectors ${r.status}`);
  return r.json();
}

export async function createSector(input: {
  name: string;
  description?: string;
  keywords?: string[];
}): Promise<SectorSummary> {
  const r = await fetch("/api/sectors", {
    method: "POST",
    headers: { "content-type": "application/json" },
    credentials: "include",
    body: JSON.stringify(input),
  });
  if (!r.ok) throw new Error(`createSector ${r.status}`);
  return r.json();
}

export async function deleteSector(id: number): Promise<void> {
  const r = await fetch(`/api/sectors/${id}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!r.ok) throw new Error(`deleteSector ${r.status}`);
}

export async function startSectorRun(
  sectorId: number,
  payload: { llm_quick_model?: string; llm_deep_model?: string } = {},
): Promise<SectorRun> {
  const r = await fetch(`/api/sectors/${sectorId}/runs`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  if (!r.ok) throw new Error(`startSectorRun ${r.status}`);
  return r.json();
}

export async function getLatestReport(sectorId: number): Promise<SectorReport | null> {
  const r = await fetch(`/api/sectors/${sectorId}/reports/latest`, {
    credentials: "include",
  });
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`getLatestReport ${r.status}`);
  return r.json();
}
```

- [ ] **Step 3: `sector-card.tsx`**

`web/components/sector/sector-card.tsx`:

```tsx
import Link from "next/link";

import type { SectorSummary } from "@/lib/sectors";

interface Props {
  sector: SectorSummary;
}

export function SectorCard({ sector }: Props) {
  const latest = sector.latest_report_at
    ? new Date(sector.latest_report_at).toLocaleDateString("ko-KR")
    : "리포트 없음";
  return (
    <Link
      href={`/sectors/${sector.slug}`}
      className="block rounded-2xl border border-bg-2 bg-bg-1 p-5 hover:border-accent-500 transition"
    >
      <div className="flex items-baseline justify-between">
        <h3 className="text-lg font-semibold">{sector.name}</h3>
        {sector.is_preset && (
          <span className="text-xs text-fg-3">프리셋</span>
        )}
      </div>
      {sector.description && (
        <p className="mt-1 text-sm text-fg-2 line-clamp-2">{sector.description}</p>
      )}
      <div className="mt-3 flex items-center gap-2 text-xs text-fg-3">
        <span>최신 리포트: {latest}</span>
        {sector.latest_report_version != null && (
          <span>v{sector.latest_report_version}</span>
        )}
      </div>
    </Link>
  );
}
```

- [ ] **Step 4: `/sectors/page.tsx`**

`web/app/(workspace)/sectors/page.tsx`:

```tsx
"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { SectorCard } from "@/components/sector/sector-card";
import { listSectors } from "@/lib/sectors";

export default function SectorsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["sectors"],
    queryFn: listSectors,
  });

  return (
    <div className="px-6 py-6 md:px-8">
      <div className="mb-6 flex items-baseline justify-between">
        <h1 className="text-2xl font-bold">산업 · 섹터</h1>
        <Link
          href="/sectors/new"
          className="rounded-lg bg-accent-500 px-4 py-2 text-sm font-medium text-white hover:bg-accent-600"
        >
          + 새 섹터
        </Link>
      </div>

      {isLoading && <p className="text-fg-3">로딩 중…</p>}
      {error && <p className="text-rose-500">로드 실패: {String(error)}</p>}

      {data && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {data.map((s) => <SectorCard key={s.id} sector={s} />)}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: 수동 확인**

```bash
WEB_FAKE_RUNNER=true uv run uvicorn tradingagents_web.main:app --port 8000 &
cd web && npm run dev
```

브라우저에서 `/sectors`에 6개 프리셋 카드가 보이는지 확인.

- [ ] **Step 6: 커밋**

```bash
git add web/package.json web/package-lock.json web/lib/sectors.ts \
        web/components/sector/sector-card.tsx \
        web/app/\(workspace\)/sectors/page.tsx
git commit -m "feat(sector): /sectors list page + types/fetchers"
```

---

## Task 18: 프런트 — `/sectors/new` 폼

**Files:**
- Create: `web/app/(workspace)/sectors/new/page.tsx`

- [ ] **Step 1: 페이지 작성**

```tsx
"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { createSector } from "@/lib/sectors";

export default function NewSectorPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [keywords, setKeywords] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const created = await createSector({
        name: name.trim(),
        description: description.trim() || undefined,
        keywords: keywords.split(",").map((k) => k.trim()).filter(Boolean),
      });
      router.push(`/sectors/${created.slug}`);
    } catch (err: any) {
      setError(err.message ?? "생성 실패");
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="mx-auto max-w-xl px-6 py-6 md:px-8">
      <h1 className="mb-6 text-2xl font-bold">새 섹터</h1>

      <label className="mb-4 block">
        <span className="mb-1 block text-sm font-medium">이름 *</span>
        <input
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full rounded-lg border border-bg-2 bg-bg-1 px-3 py-2"
        />
      </label>

      <label className="mb-4 block">
        <span className="mb-1 block text-sm font-medium">설명</span>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={3}
          className="w-full rounded-lg border border-bg-2 bg-bg-1 px-3 py-2"
        />
      </label>

      <label className="mb-6 block">
        <span className="mb-1 block text-sm font-medium">키워드 (쉼표 구분)</span>
        <input
          value={keywords}
          onChange={(e) => setKeywords(e.target.value)}
          placeholder="ex) GPU, AI accelerator, NVIDIA"
          className="w-full rounded-lg border border-bg-2 bg-bg-1 px-3 py-2"
        />
      </label>

      {error && <p className="mb-4 text-sm text-rose-500">{error}</p>}

      <button
        type="submit"
        disabled={submitting || !name.trim()}
        className="rounded-lg bg-accent-500 px-4 py-2 text-sm font-medium text-white hover:bg-accent-600 disabled:opacity-50"
      >
        {submitting ? "생성 중…" : "생성"}
      </button>
    </form>
  );
}
```

- [ ] **Step 2: 수동 확인**

`/sectors/new`에서 "양자 컴퓨팅" 정도 입력 후 생성 → `/sectors/yang...` 으로 리다이렉트.

- [ ] **Step 3: 커밋**

```bash
git add web/app/\(workspace\)/sectors/new/page.tsx
git commit -m "feat(sector): /sectors/new creation form"
```

---

## Task 19: 프런트 — `value-chain-diagram` (mermaid)

**Files:**
- Create: `web/components/sector/value-chain-diagram.tsx`

- [ ] **Step 1: 컴포넌트 작성 (mermaid dynamic import)**

```tsx
"use client";

import { useEffect, useRef, useState } from "react";

interface Props {
  mermaid: string;
}

export function ValueChainDiagram({ mermaid }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!mermaid.trim()) return;

    (async () => {
      try {
        const m = (await import("mermaid")).default;
        m.initialize({ startOnLoad: false, theme: "neutral", securityLevel: "strict" });
        const id = `vc-${Date.now()}`;
        const { svg } = await m.render(id, mermaid);
        if (!cancelled && ref.current) ref.current.innerHTML = svg;
      } catch (err: any) {
        if (!cancelled) setError(err?.message ?? "mermaid render failed");
      }
    })();
    return () => { cancelled = true; };
  }, [mermaid]);

  if (!mermaid.trim()) {
    return <p className="text-sm text-fg-3">가치사슬 다이어그램 없음</p>;
  }
  if (error) {
    return (
      <div className="rounded-lg border border-rose-300 bg-rose-50 p-3 text-sm text-rose-700">
        <p className="font-medium">다이어그램 렌더 실패</p>
        <pre className="mt-2 overflow-x-auto text-xs">{mermaid}</pre>
      </div>
    );
  }
  return <div ref={ref} className="w-full overflow-x-auto" />;
}
```

- [ ] **Step 2: 커밋**

```bash
git add web/components/sector/value-chain-diagram.tsx
git commit -m "feat(sector): mermaid value-chain diagram with dynamic import + fallback"
```

---

## Task 20: 프런트 — `companies-table`

**Files:**
- Create: `web/components/sector/companies-table.tsx`

- [ ] **Step 1: 컴포넌트 작성**

```tsx
"use client";

import { useMemo, useState } from "react";

import type { CompanyShare } from "@/lib/sectors";

const BASIS_LABEL: Record<CompanyShare["share_basis"], string> = {
  reported: "공시",
  estimated: "추정",
  unknown: "불명",
};

const BASIS_COLOR: Record<CompanyShare["share_basis"], string> = {
  reported: "bg-emerald-100 text-emerald-700",
  estimated: "bg-amber-100 text-amber-700",
  unknown: "bg-slate-100 text-slate-600",
};

export function CompaniesTable({ companies }: { companies: CompanyShare[] }) {
  const stages = useMemo(() => {
    const map = new Map<string, CompanyShare[]>();
    for (const c of companies) {
      const list = map.get(c.stage) ?? [];
      list.push(c);
      map.set(c.stage, list);
    }
    for (const list of map.values()) list.sort((a, b) => b.share_value - a.share_value);
    return [...map.entries()];
  }, [companies]);

  if (companies.length === 0) {
    return <p className="text-sm text-fg-3">기업 데이터 없음</p>;
  }

  return (
    <div className="space-y-6">
      {stages.map(([stage, list]) => (
        <section key={stage} data-stage={stage}>
          <h3 className="mb-2 text-sm font-semibold text-fg-2">{stage}</h3>
          <div className="overflow-x-auto rounded-lg border border-bg-2">
            <table className="min-w-full text-sm">
              <thead className="bg-bg-1 text-fg-3">
                <tr>
                  <th className="px-3 py-2 text-left">기업</th>
                  <th className="px-3 py-2 text-right">점유율</th>
                  <th className="px-3 py-2 text-left">근거</th>
                  <th className="px-3 py-2 text-left">출처</th>
                </tr>
              </thead>
              <tbody>
                {list.map((c) => (
                  <CompanyRow key={`${c.stage}-${c.name}`} c={c} />
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </div>
  );
}

function CompanyRow({ c }: { c: CompanyShare }) {
  const [showSources, setShowSources] = useState(false);
  return (
    <tr className="border-t border-bg-2">
      <td className="px-3 py-2">
        <span className="font-medium">{c.name}</span>
        {c.ticker && <span className="ml-2 text-fg-3">({c.ticker})</span>}
      </td>
      <td className="px-3 py-2 text-right font-mono">{c.share_value.toFixed(1)}%</td>
      <td className="px-3 py-2">
        <span className={`rounded px-2 py-0.5 text-xs ${BASIS_COLOR[c.share_basis]}`}>
          {BASIS_LABEL[c.share_basis]} · {c.confidence}
        </span>
      </td>
      <td className="px-3 py-2">
        {c.sources.length === 0 ? (
          <span className="text-fg-3">—</span>
        ) : (
          <div className="relative">
            <button
              type="button"
              onClick={() => setShowSources((v) => !v)}
              className="text-accent-500 hover:underline"
            >
              {c.sources.length}건
            </button>
            {showSources && (
              <ul className="absolute z-10 mt-1 w-72 rounded-lg border border-bg-2 bg-bg-0 p-2 text-xs shadow-lg">
                {c.sources.map((u, i) => (
                  <li key={i} className="truncate">
                    <a href={u} target="_blank" rel="noopener noreferrer"
                       className="text-accent-500 hover:underline">{u}</a>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </td>
    </tr>
  );
}
```

- [ ] **Step 2: 커밋**

```bash
git add web/components/sector/companies-table.tsx
git commit -m "feat(sector): companies-table with basis badges + sources popover"
```

---

## Task 21: 프런트 — `candidate-tickers`

**Files:**
- Create: `web/components/sector/candidate-tickers.tsx`

- [ ] **Step 1: 컴포넌트 작성**

```tsx
"use client";

import Link from "next/link";

import type { CandidateTicker } from "@/lib/sectors";

interface Props {
  candidates: CandidateTicker[];
  fromSectorSlug: string;
  fromReportId: number;
}

export function CandidateTickers({ candidates, fromSectorSlug, fromReportId }: Props) {
  if (candidates.length === 0) {
    return <p className="text-sm text-fg-3">후보 종목 없음</p>;
  }
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
      {candidates.map((c) => (
        <div key={c.ticker} className="rounded-lg border border-bg-2 bg-bg-1 p-4">
          <div className="flex items-baseline justify-between gap-3">
            <div>
              <h4 className="font-semibold">{c.name}</h4>
              <p className="text-xs text-fg-3">{c.ticker} · {c.stage}</p>
            </div>
            <Link
              href={{
                pathname: "/run",
                query: {
                  ticker: c.ticker,
                  from_sector: fromSectorSlug,
                  from_report: fromReportId,
                },
              }}
              className="shrink-0 rounded-lg bg-accent-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-600"
            >
              종목 분석
            </Link>
          </div>
          <p className="mt-2 text-sm text-fg-2">{c.reason}</p>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: 커밋**

```bash
git add web/components/sector/candidate-tickers.tsx
git commit -m "feat(sector): candidate-tickers cards linking to /run prefill"
```

---

## Task 22: 프런트 — `/sectors/[slug]` 리포트 페이지

**Files:**
- Create: `web/app/(workspace)/sectors/[slug]/page.tsx`
- Modify: `web/lib/sectors.ts` (`getSector`, `getReportsList`)

- [ ] **Step 1: 페처 추가**

`web/lib/sectors.ts` 끝에:

```typescript
export async function getSectorBySlug(slug: string): Promise<SectorSummary | null> {
  const all = await listSectors();
  return all.find((s) => s.slug === slug) ?? null;
}

export interface SectorReportSummary {
  id: number;
  version: number;
  created_at: string;
}

export async function listReports(sectorId: number): Promise<SectorReportSummary[]> {
  const r = await fetch(`/api/sectors/${sectorId}/reports`, { credentials: "include" });
  if (!r.ok) throw new Error(`listReports ${r.status}`);
  return r.json();
}

export async function getReport(sectorId: number, reportId: number): Promise<SectorReport> {
  const r = await fetch(`/api/sectors/${sectorId}/reports/${reportId}`, {
    credentials: "include",
  });
  if (!r.ok) throw new Error(`getReport ${r.status}`);
  return r.json();
}
```

- [ ] **Step 2: 페이지 작성**

`web/app/(workspace)/sectors/[slug]/page.tsx`:

```tsx
"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { use, useState } from "react";
import ReactMarkdown from "react-markdown";

import { CandidateTickers } from "@/components/sector/candidate-tickers";
import { CompaniesTable } from "@/components/sector/companies-table";
import { ValueChainDiagram } from "@/components/sector/value-chain-diagram";
import {
  getReport,
  getSectorBySlug,
  listReports,
  startSectorRun,
} from "@/lib/sectors";

export default function SectorDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  const router = useRouter();
  const [selectedReportId, setSelectedReportId] = useState<number | null>(null);

  const sector = useQuery({
    queryKey: ["sector", slug],
    queryFn: () => getSectorBySlug(slug),
  });

  const reports = useQuery({
    queryKey: ["sector-reports", sector.data?.id],
    queryFn: () => listReports(sector.data!.id),
    enabled: !!sector.data,
  });

  const activeReportId = selectedReportId ?? reports.data?.[0]?.id ?? null;

  const report = useQuery({
    queryKey: ["sector-report", activeReportId],
    queryFn: () => getReport(sector.data!.id, activeReportId!),
    enabled: !!sector.data && !!activeReportId,
  });

  const startRun = useMutation({
    mutationFn: () => startSectorRun(sector.data!.id),
    onSuccess: (run) => router.push(`/sectors/${slug}/runs/${run.id}`),
  });

  if (sector.isLoading) return <p className="px-6 py-6">로딩 중…</p>;
  if (!sector.data) return <p className="px-6 py-6">섹터를 찾을 수 없습니다.</p>;

  return (
    <div className="mx-auto max-w-5xl px-6 py-6 md:px-8">
      <header className="mb-6 flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">{sector.data.name}</h1>
          {sector.data.description && (
            <p className="mt-1 text-fg-2">{sector.data.description}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {reports.data && reports.data.length > 0 && (
            <select
              value={activeReportId ?? ""}
              onChange={(e) => setSelectedReportId(Number(e.target.value))}
              className="rounded-lg border border-bg-2 bg-bg-1 px-3 py-2 text-sm"
            >
              {reports.data.map((r) => (
                <option key={r.id} value={r.id}>
                  v{r.version} · {new Date(r.created_at).toLocaleDateString("ko-KR")}
                </option>
              ))}
            </select>
          )}
          <button
            type="button"
            onClick={() => startRun.mutate()}
            disabled={startRun.isPending}
            className="rounded-lg bg-accent-500 px-4 py-2 text-sm font-medium text-white hover:bg-accent-600 disabled:opacity-50"
          >
            {startRun.isPending ? "시작 중…" : "리포트 새로 생성"}
          </button>
        </div>
      </header>

      {reports.data && reports.data.length === 0 && (
        <p className="rounded-lg bg-bg-1 p-6 text-fg-2">
          아직 리포트가 없습니다. "리포트 새로 생성" 버튼으로 시작하세요.
        </p>
      )}

      {report.data && (
        <article className="space-y-8">
          <section>
            <h2 className="mb-2 text-lg font-semibold">가치사슬</h2>
            <div className="rounded-lg border border-bg-2 bg-bg-1 p-4">
              <ValueChainDiagram mermaid={report.data.value_chain_mermaid} />
            </div>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-semibold">단계별 핵심 기업</h2>
            <CompaniesTable companies={report.data.companies} />
          </section>

          <section>
            <h2 className="mb-2 text-lg font-semibold">투자 전망</h2>
            <div className="prose prose-sm dark:prose-invert max-w-none rounded-lg border border-bg-2 bg-bg-1 p-4">
              <ReactMarkdown>{report.data.outlook_summary}</ReactMarkdown>
            </div>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-semibold">후보 종목</h2>
            <CandidateTickers
              candidates={report.data.candidate_tickers}
              fromSectorSlug={sector.data.slug}
              fromReportId={report.data.id}
            />
          </section>

          <details className="rounded-lg border border-bg-2 bg-bg-1 p-4">
            <summary className="cursor-pointer text-sm font-medium">전체 리포트 (원문)</summary>
            <div className="prose prose-sm dark:prose-invert mt-3 max-w-none">
              <ReactMarkdown>{report.data.report_md}</ReactMarkdown>
            </div>
          </details>
        </article>
      )}
    </div>
  );
}
```

- [ ] **Step 3: 수동 확인**

`/sectors/ai`에서 빈 상태 → "리포트 새로 생성" 클릭 → `/sectors/ai/runs/<rid>`로 이동(다음 Task에서 페이지 작성).

- [ ] **Step 4: 커밋**

```bash
git add web/lib/sectors.ts web/app/\(workspace\)/sectors/\[slug\]/page.tsx
git commit -m "feat(sector): /sectors/[slug] report viewer with version selector"
```

---

## Task 23: 프런트 — `/sectors/[slug]/runs/[rid]` SSE 진행 페이지

**Files:**
- Create: `web/components/sector/phase-progress.tsx`
- Create: `web/app/(workspace)/sectors/[slug]/runs/[rid]/page.tsx`
- Create: `web/app/api/sectors/[id]/runs/[rid]/stream/route.ts` (SSE 프록시)

- [ ] **Step 1: Next.js SSE 프록시 라우트**

기존 종목용 `/web/app/api/runs/[id]/stream/route.ts`와 같은 형태로:

`web/app/api/sectors/[id]/runs/[rid]/stream/route.ts`:

```typescript
import { NextRequest } from "next/server";

const BACKEND = process.env.API_BACKEND_URL ?? "http://localhost:8000";

export async function GET(
  req: NextRequest,
  context: { params: Promise<{ id: string; rid: string }> },
) {
  const { id, rid } = await context.params;
  const cookie = req.headers.get("cookie") ?? "";
  const upstream = await fetch(`${BACKEND}/api/sectors/${id}/runs/${rid}/stream`, {
    headers: { cookie, accept: "text/event-stream" },
  });
  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "content-type": "text/event-stream",
      "cache-control": "no-cache",
      "x-accel-buffering": "no",
    },
  });
}
```

- [ ] **Step 2: phase-progress 컴포넌트**

`web/components/sector/phase-progress.tsx`:

```tsx
"use client";

const PHASES: { key: string; label: string }[] = [
  { key: "macro", label: "거시 환경" },
  { key: "value_chain", label: "가치사슬" },
  { key: "competitive", label: "경쟁 구도" },
  { key: "outlook", label: "투자 전망" },
];

export function PhaseProgress({ current }: { current: string | null }) {
  const currentIdx = current ? PHASES.findIndex((p) => p.key === current) : -1;
  return (
    <ol className="flex items-center gap-2">
      {PHASES.map((p, i) => {
        const done = i < currentIdx;
        const active = i === currentIdx;
        return (
          <li key={p.key} className="flex flex-1 items-center gap-2">
            <div
              className={[
                "flex h-7 w-7 items-center justify-center rounded-full text-xs font-medium",
                done ? "bg-emerald-500 text-white"
                  : active ? "bg-accent-500 text-white animate-pulse"
                  : "bg-bg-2 text-fg-3",
              ].join(" ")}
            >
              {i + 1}
            </div>
            <span className={active ? "text-fg-0 font-medium" : "text-fg-3"}>
              {p.label}
            </span>
            {i < PHASES.length - 1 && (
              <div className={`h-px flex-1 ${done ? "bg-emerald-500" : "bg-bg-2"}`} />
            )}
          </li>
        );
      })}
    </ol>
  );
}
```

- [ ] **Step 3: 진행 페이지**

`web/app/(workspace)/sectors/[slug]/runs/[rid]/page.tsx`:

```tsx
"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { use, useEffect, useState } from "react";

import { PhaseProgress } from "@/components/sector/phase-progress";
import { getSectorBySlug } from "@/lib/sectors";

export default function SectorRunPage({
  params,
}: {
  params: Promise<{ slug: string; rid: string }>;
}) {
  const { slug, rid } = use(params);
  const router = useRouter();
  const [phase, setPhase] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sector = useQuery({
    queryKey: ["sector", slug],
    queryFn: () => getSectorBySlug(slug),
  });

  useEffect(() => {
    if (!sector.data) return;
    const es = new EventSource(`/api/sectors/${sector.data.id}/runs/${rid}/stream`);

    es.addEventListener("progress", (ev) => {
      try {
        const p = JSON.parse((ev as MessageEvent).data);
        setPhase(p.phase);
      } catch { /* ignore */ }
    });
    es.addEventListener("completed", () => {
      setDone(true);
      es.close();
      setTimeout(() => router.push(`/sectors/${slug}`), 800);
    });
    es.addEventListener("error", () => {
      setError("분석 도중 오류가 발생했습니다.");
      es.close();
    });
    return () => es.close();
  }, [sector.data, rid, router, slug]);

  return (
    <div className="mx-auto max-w-3xl px-6 py-10 md:px-8">
      <h1 className="mb-6 text-xl font-bold">
        {sector.data?.name ?? "산업"} 분석 진행 중…
      </h1>
      <div className="rounded-2xl border border-bg-2 bg-bg-1 p-6">
        <PhaseProgress current={phase} />
      </div>
      {done && <p className="mt-4 text-emerald-500">완료! 리포트로 이동합니다…</p>}
      {error && <p className="mt-4 text-rose-500">{error}</p>}
    </div>
  );
}
```

- [ ] **Step 4: 수동 확인**

`WEB_FAKE_RUNNER=true`로 백엔드 + 프런트 띄우고 `/sectors/ai`에서 "리포트 새로 생성" → 4 페이즈가 0.5s 간격으로 진행되고 자동으로 `/sectors/ai`로 돌아가 더미 리포트가 보이는지.

- [ ] **Step 5: 커밋**

```bash
git add web/app/api/sectors/ web/components/sector/phase-progress.tsx \
        web/app/\(workspace\)/sectors/\[slug\]/runs/
git commit -m "feat(sector): SSE progress page + Next.js stream proxy"
```

---

## Task 24: `/run` 페이지 prefill

**Files:**
- Modify: `web/app/(workspace)/run/page.tsx`

- [ ] **Step 1: 기존 페이지 점검**

`web/app/(workspace)/run/page.tsx`를 열어 ticker 입력 컴포넌트를 찾고, `useSearchParams()`로 `ticker`, `from_sector`, `from_report` 쿼리를 읽어 prefill.

- [ ] **Step 2: 코드 수정 (변경 위치 표시)**

페이지 상단에 useSearchParams 훅 import 추가 후 useEffect로 prefill:

```tsx
import { useSearchParams } from "next/navigation";
// ...
const search = useSearchParams();
const fromSector = search.get("from_sector");
const fromReport = search.get("from_report");
const prefillTicker = search.get("ticker") ?? "";

useEffect(() => {
  if (prefillTicker) setTicker(prefillTicker);
}, [prefillTicker]);
```

폼 상단에 안내 텍스트:

```tsx
{fromSector && (
  <div className="mb-4 rounded-lg border border-accent-300 bg-accent-50 p-3 text-sm text-accent-700">
    산업 리포트 <Link href={`/sectors/${fromSector}`} className="underline">{fromSector}</Link>
    {fromReport && ` (v${fromReport})`}에서 시작
  </div>
)}
```

- [ ] **Step 3: 수동 확인**

`/sectors/ai`의 후보 종목 카드 → "종목 분석" → `/run?ticker=NVDA&from_sector=ai&from_report=1`로 이동하고 ticker가 채워지고 안내 텍스트 표시.

- [ ] **Step 4: 커밋**

```bash
git add web/app/\(workspace\)/run/page.tsx
git commit -m "feat(sector): prefill /run from candidate ticker click"
```

---

## Task 25: Sidebar / TabBar 메뉴 추가

**Files:**
- Modify: `web/components/nav/sidebar.tsx`
- Modify: `web/components/nav/tab-bar.tsx`

- [ ] **Step 1: Sidebar 항목 추가**

`web/components/nav/sidebar.tsx` Workspace 섹션 배열에 추가 (정확한 키 이름은 파일을 열어 확인):

```tsx
{ label: "Sectors", href: "/sectors", icon: <SectorsIcon /> },
```

(아이콘은 lucide-react의 `Layers` 또는 `Network` 적당히 사용.)

- [ ] **Step 2: 모바일 탭바 추가**

`web/components/nav/tab-bar.tsx`의 탭 배열에 5번째 항목으로 추가하거나 `/more` 메뉴로 보강. 화면 폭 고려해 결정. 권장: `/more` 메뉴에 추가.

`web/app/(workspace)/more/page.tsx`(이미 있음)에 Sectors 카드 추가.

- [ ] **Step 3: 수동 확인**

데스크톱·모바일 양쪽에서 진입 가능 확인.

- [ ] **Step 4: 커밋**

```bash
git add web/components/nav/sidebar.tsx web/components/nav/tab-bar.tsx \
        web/app/\(workspace\)/more/page.tsx
git commit -m "feat(sector): add Sectors nav entry to sidebar + more"
```

---

## Task 26: E2E Playwright

**Files:**
- Create: `web/tests/e2e/sectors.spec.ts`

- [ ] **Step 1: E2E 시나리오 작성**

```typescript
import { expect, test } from "@playwright/test";

test.describe("Sectors", () => {
  test("프리셋 → 분석 실행 → 후보 종목 → /run prefill", async ({ page }) => {
    await page.goto("/sectors");
    await expect(page.getByText("AI · 인공지능")).toBeVisible();

    await page.getByText("AI · 인공지능").click();
    await expect(page).toHaveURL(/\/sectors\/ai/);

    await page.getByRole("button", { name: "리포트 새로 생성" }).click();
    await expect(page).toHaveURL(/\/sectors\/ai\/runs\//);

    // 4 페이즈가 진행되고 자동 redirect
    await page.waitForURL(/\/sectors\/ai(?:\?|$)/, { timeout: 10_000 });

    // 더미 후보 종목 카드 클릭
    const nvda = page.getByRole("link", { name: "종목 분석" }).first();
    await nvda.click();

    // /run prefill 확인
    await expect(page).toHaveURL(/\/run\?.*ticker=NVDA.*from_sector=ai/);
    await expect(page.getByText("산업 리포트")).toBeVisible();
  });

  test("프리셋 삭제 불가 — 409", async ({ page, request }) => {
    const list = await request.get("/api/sectors");
    const ai = (await list.json()).find((s: any) => s.slug === "ai");
    const r = await request.delete(`/api/sectors/${ai.id}`);
    expect(r.status()).toBe(409);
  });
});
```

- [ ] **Step 2: E2E 실행**

`scripts/setup_e2e.sh`로 격리 DB 시드 후:

```bash
cd web && npm run e2e -- sectors
```

- [ ] **Step 3: 커밋**

```bash
git add web/tests/e2e/sectors.spec.ts
git commit -m "test(sector): e2e flow — list → run → candidate → /run prefill"
```

---

## Task 27: 환경/문서 업데이트

**Files:**
- Modify: `DEV.md`
- Modify: `README.md`
- Modify: `.env.example` (Task 1에서 일부 적용, 보완)

- [ ] **Step 1: `DEV.md`에 새 섹션 추가**

`DEV.md` 끝에:

```markdown
## M6 — Sector Industry Analysis

새 의존성: `tavily-python>=0.5`(백엔드), `mermaid@^11`(프런트). 기존 `uv sync` + `(cd web && npm install)` 후 사용 가능.

### 환경 변수

| 이름 | 기본값 | 설명 |
|---|---|---|
| `TAVILY_API_KEY` | (필수) | Tavily 웹검색 API 키. 미설정 시 분석 시작에서 503 |
| `SECTOR_SEARCH_BUDGET` | `12` | 한 번의 산업 분석 전체에서 web_search 도구 호출 상한 |
| `SECTOR_NODE_SEARCH_BUDGET` | `3` | 노드(거시/가치사슬/경쟁) 1개당 web_search 호출 상한 |

### 사용 흐름

1. `/sectors`에서 프리셋 6종(AI · 전력 · 메모리/비메모리 반도체 · 로봇 · 우주) 또는 사용자 정의 섹터 선택.
2. `/sectors/<slug>`에서 "리포트 새로 생성" → 4단계 그래프(거시→가치사슬→경쟁구도→투자전망)가 SSE phase 진행으로 표시.
3. 완료 후 가치사슬 mermaid 다이어그램, 단계별 기업 점유율 표(공시/추정/불명 배지), 후보 종목 카드 확인.
4. 후보 종목 카드의 "종목 분석" 버튼 → `/run?ticker=…&from_sector=…&from_report=…`로 기존 종목 분석 폼 진입.

### 주의

- 점유율 수치는 **모두 LLM + 웹검색 종합 결과**. `share_basis=reported`라도 출처 URL을 직접 클릭해 검증 권장.
- `WEB_FAKE_RUNNER=true`로 LLM/Tavily 호출 없이 UI·SSE·DB 흐름을 검증 가능 — 더미 리포트가 즉시 생성된다.
- 동일 섹터에 이미 `status=running`인 분석이 있으면 새 실행은 409.
- 프리셋 섹터는 삭제 불가(409). 사용자 정의는 삭제 가능하며 cascade로 리포트·실행 기록도 함께 사라진다.
```

- [ ] **Step 2: `README.md`에 짧은 섹션 추가**

`### Schedules · Alerts · Notifications` 다음에:

```markdown
### Sectors — 산업/섹터 분석

AI · 전력 · 반도체(메모리/비메모리) · 로봇 · 우주 같은 산업을 선택하면 4단계 LangGraph 그래프가 거시 환경·가치사슬·경쟁 구도·투자 전망 보고서를 생성합니다. 가치사슬은 mermaid 다이어그램, 단계별 기업 점유율은 공시/추정/불명 배지와 출처 URL로 분리되어 신뢰성을 명시합니다. 후보 종목 카드의 "종목 분석" 버튼이 기존 `/run` 폼으로 prefill되며 산업 → 종목 드릴다운 흐름을 자연스럽게 잇습니다.

웹 검색은 Tavily를 사용하며 노드당 3회·전체 12회 호출 가드로 비용 폭주를 막습니다. `WEB_FAKE_RUNNER=true`로 LLM/Tavily 호출 없이 흐름 검증 가능.
```

- [ ] **Step 3: 커밋**

```bash
git add DEV.md README.md
git commit -m "docs(sector): document M6 sector analysis setup + flow"
```

---

## Self-Review

**1. Spec coverage:**
- 데이터 모델 (Sector / SectorRun / SectorReport) → Task 2-3
- Pydantic 스키마 → Task 4
- web_search 도구 + 가드 → Task 5
- 4단계 그래프 (Macro / ValueChain / Competitive / Outlook) → Task 6-11
- Runner & SSE (Fake + Real) → Task 12-13
- API (CRUD + runs + reports) → Task 14-16
- 프런트 (목록 / 신규 / 다이어그램 / 표 / 후보 / 상세 / 진행) → Task 17-23
- /run prefill → Task 24
- 내비게이션 → Task 25
- E2E → Task 26
- 환경/문서 → Task 27 ✓

**2. Placeholder 스캔:** 모든 step에 실행 가능한 코드/명령. `<직전 head>`는 Task 3의 실제 alembic heads 값으로 교체해야 함 — 실행 시점에 결정되므로 그대로 둠.

**3. Type 일관성:**
- `SectorState.budget: SearchBudget` (Task 5, 6) ✓
- `make_*_node(llm, budget)` signature (Task 7, 8, 9) ↔ `make_investment_outlook_node(llm)` (Task 10, outlook은 budget 없음) ✓ — 의도된 차이.
- `_NODE_TO_PHASE` (Task 13) ↔ 그래프 노드명 (Task 11) ✓
- `SectorRunRequest` / `SectorRunResult` (Task 12) ↔ Real runner (Task 13) ↔ API background task (Task 15) ✓
- `share_basis` Literal 값 `reported|estimated|unknown` (Task 4) ↔ 노드 정규화 (Task 9) ↔ 프런트 BASIS_LABEL (Task 20) ✓

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-28-sector-industry-analysis.md`.**

두 가지 실행 옵션:

**1. Subagent-Driven (recommended)** — task마다 fresh subagent를 dispatch, 사이에 review, 빠른 반복

**2. Inline Execution** — 현재 세션에서 `superpowers:executing-plans` 스킬로 batch 실행 + 체크포인트

어떤 방식으로 진행할까요?
