# TradingAgents Web — M4 Alerts + Telegram Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 분석이 끝날 때마다 직전 결과와 비교해 시그널 변경(BUY⇄HOLD⇄SELL)·큰 신뢰도 변화·실행 실패·스케줄 실패를 감지하고, `alerts` 테이블에 영구 기록함과 동시에 사용자가 활성화한 채널(in-app, Telegram)로 푸시한다. 사용자는 `/alerts`에서 알림 히스토리를 보고, `/settings/notifications`에서 봇 토큰·임계값을 관리한다.

**Architecture:** SQLite에 `alerts`, `settings` 테이블을 추가한다. `_execute_and_persist`(M2 runner) 종료 분기와 APScheduler 트리거 실패 분기가 공통 디스패처 `services.notifier.dispatch_for_analysis()` / `dispatch_schedule_failure()`를 호출한다. 디스패처는 (1) 직전 동일 티커 완료 분석 row를 조회해 `services.signal_diff.diff_for_completion()` 순수 함수에 위임, (2) 트리거 결과를 `alerts` 행으로 영구 기록, (3) `Setting` 테이블에서 사용자가 켠 채널·암호화된 봇 토큰을 읽어 `services.telegram.send_message()`(httpx async)를 fire-and-forget으로 호출한다. 알림 설정은 한 행 = 한 키 패턴(`Setting(key, value, encrypted_value)`)으로 저장하며, `telegram_bot_token`만 Fernet 암호화. 프런트엔드는 `/alerts` 페이지(필터 + 읽음 토글), `/settings/notifications` 페이지, 그리고 워크스페이스 헤더의 미읽음 카운트 벨 아이콘을 추가한다.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, alembic, `cryptography.Fernet`(이미 설치), `httpx`(이미 설치, async 클라이언트), pytest, `respx`(httpx 모킹). Next.js 14 App Router, TypeScript, TanStack Query.

**Spec:** [docs/superpowers/specs/2026-04-25-tradingagents-web-design.md](../specs/2026-04-25-tradingagents-web-design.md) — §2 S5, §3(`/alerts`, `/settings/notifications`), §6(`alerts`, `settings`), §8(전체), §11(M4)

**Out of scope (다른 플랜에서):**
- 비교 뷰 `/history/compare` (M5)
- PWA 매니페스트 / Service Worker (M5)
- LLM/Data 설정 UI (`/settings/llm`, `/settings/data`, `/settings/account`) — M4는 Notifications 설정만
- 다중 채널(이메일/Slack 등) — 현재 spec은 Telegram + in-app 만 명시
- Telegram bot의 인바운드 명령 처리 — push만 함

**의존 결정 (open issues §14에 영향 받는 부분):**

1. **Settings 저장 모양** → 한 행 = 한 키. Pydantic 응답에서 도메인 객체로 합성. 봇 토큰만 `encrypted_value`(bytes), 나머지는 `value`(text JSON). 응답에서 토큰은 `***`로 마스킹하고 별도 `telegram_bot_token_set: bool` 필드로 존재 여부만 노출.
2. **시그널 변경 비교 대상** → 같은 티커의 직전 `completed` 행(현재 분석을 제외하고 가장 가까운 `created_at`). 첫 분석은 비교 대상 없음 → 시그널 변경 알림 없음(`run_completed`만 사용자 토글에 따라 발송).
3. **알림 트리거 호출 지점** → `runs.py:_execute_and_persist` 안의 두 분기(commit 직후 success / failure exception 핸들러)에서 `await notifier.dispatch_for_analysis(run_id)` 호출. 스케줄 실패는 `auto_runner.trigger_run` 예외 핸들러에서 `dispatch_schedule_failure(schedule_id, error)`. 알림 dispatch는 자체 try/except로 감싸 메인 흐름을 절대 깨지 않는다.
4. **Telegram 클라이언트** → `httpx.AsyncClient`. `python-telegram-bot` 풀체인은 과대(스케줄러/업데이트 큐 등). spec §13의 deps 목록은 의도이지 강제 아님 — 실제로는 `httpx`만으로 `sendMessage` POST가 충분.
5. **임계값 기본값** → `confidence_change_threshold = 0.10`(±10%, spec §8.1.2). `alert_on_signal_change=True`, `alert_on_run_failed=True`, `alert_on_schedule_failed=True`, `alert_on_run_completed=False`(시끄러우니까 OFF, spec §8.1.3).
6. **읽음 처리** → `read: bool` 컬럼 + 단일 endpoint `POST /api/alerts/{id}/read` 와 일괄 `POST /api/alerts/read-all`. 미읽음 카운트는 `GET /api/alerts/unread-count`(저비용, 30s 폴링).
7. **봇 토큰 검증** → `POST /api/settings/notifications/test`가 새로 입력된(또는 저장된) 토큰으로 `getMe`를 호출해 200/`ok=true` 검증, 실패 시 422 반환.
8. **테스트에서 telegram 호출 차단** → `services.telegram.send_message`를 모듈 레벨 함수로 두고 pytest 픽스처에서 `monkeypatch.setattr`로 no-op 또는 `respx`로 HTTP 인터셉트.

---

## File Structure

신규 백엔드:

```
tradingagents_web/
├── models/
│   ├── alert.py              # Alert ORM
│   └── setting.py            # Setting ORM (key-value, encrypted_value)
├── schemas/
│   ├── alert.py
│   └── notification.py
├── services/
│   ├── signal_diff.py        # 순수 함수: 직전 분석과 비교
│   ├── notifier.py           # 알림 디스패처 (DB + telegram)
│   ├── telegram.py           # httpx 기반 Telegram Bot API 클라이언트
│   └── settings_store.py     # Setting 행 read/write 헬퍼 (암호화 처리)
└── api/
    ├── alerts.py             # GET 목록/카운트, POST read/read-all
    └── settings_notifications.py  # GET/PUT/POST test

migrations/versions/
└── 0004_alerts_settings.py
```

신규 테스트:

```
tests/web/
├── test_models_alert.py
├── test_models_setting.py
├── test_schemas_alert.py
├── test_schemas_notification.py
├── test_signal_diff.py
├── test_settings_store.py
├── test_telegram_service.py
├── test_notifier.py
├── test_alerts_api.py
├── test_settings_notifications_api.py
└── test_integration_m4.py    # 분석 완료→signal change→alert row→telegram mock 호출
```

신규 프런트엔드:

```
web/
├── app/
│   └── (workspace)/
│       ├── alerts/
│       │   └── page.tsx
│       └── settings/
│           ├── layout.tsx       # 좌측 settings 서브내비
│           └── notifications/
│               └── page.tsx
├── components/
│   ├── alerts/
│   │   ├── alert-row.tsx
│   │   ├── alerts-filter-bar.tsx
│   │   └── unread-bell.tsx       # 헤더에 들어가는 벨 아이콘 + 카운트
│   └── settings/
│       └── notifications-form.tsx
├── hooks/
│   ├── use-alerts.ts
│   ├── use-unread-count.ts
│   └── use-notification-settings.ts
└── lib/
    ├── alerts.ts                 # 타입 + fetch 래퍼
    └── notification-settings.ts
```

기존 변경:

- `tradingagents_web/main.py`: alerts·settings_notifications 라우터 등록
- `tradingagents_web/models/__init__.py`: `Alert`, `Setting` export
- `tradingagents_web/api/runs.py:_execute_and_persist`: success/failure commit 직후 `await notifier.dispatch_for_analysis(...)` (try/except)
- `tradingagents_web/services/auto_runner.py:trigger_run`: 예외 시 `dispatch_schedule_failure(...)` 호출
- `web/app/(workspace)/layout.tsx`: 데스크톱 헤더 영역에 `UnreadBell` 컴포넌트 삽입
- `web/components/nav/sidebar.tsx`: Settings 항목을 `/settings/notifications`로 임시 연결(현재 `/settings/llm` 더미)
- `DEV.md`: M4 사용 절차 단락 추가
- `docs/superpowers/plans/`: 본 파일 추가 (이미 작성됨)

---

## Tasks

### Task 1: alembic 마이그레이션 0004 — alerts + settings 테이블

**Files:**
- Create: `migrations/versions/0004_alerts_settings.py`
- Test: `tests/web/test_migrations.py` (기존 파일에 케이스 추가)

- [ ] **Step 1: Read 현재 0003 마이그레이션 + test_migrations.py 형식 확인**

Run: `cat migrations/versions/0003_holdings_schedules.py | head -30`
Expected: 0003 head 확인. 새 파일은 `down_revision = "0003"`로 잇는다.

- [ ] **Step 2: 마이그레이션 파일 작성**

```python
# migrations/versions/0004_alerts_settings.py
"""alerts + settings tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-26 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=True),
        sa.Column("analysis_id", sa.Integer(), nullable=True),
        sa.Column("schedule_id", sa.Integer(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("read", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_alerts_read_created", "alerts", ["read", "created_at"])
    op.create_index("ix_alerts_ticker", "alerts", ["ticker"])
    op.create_index("ix_alerts_type", "alerts", ["type"])

    op.create_table(
        "settings",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("encrypted_value", sa.LargeBinary(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("settings")
    op.drop_index("ix_alerts_type", table_name="alerts")
    op.drop_index("ix_alerts_ticker", table_name="alerts")
    op.drop_index("ix_alerts_read_created", table_name="alerts")
    op.drop_table("alerts")
```

- [ ] **Step 3: 마이그레이션 round-trip 테스트 추가**

Edit `tests/web/test_migrations.py` — 기존 패턴을 그대로 따라 0004 검증을 추가한다. 예:

```python
def test_0004_creates_alerts_and_settings(tmp_path, run_migrations_to):
    db_path = tmp_path / "m4.db"
    engine = run_migrations_to(db_path, "0004")
    inspector = sa.inspect(engine)
    assert "alerts" in inspector.get_table_names()
    assert "settings" in inspector.get_table_names()
    cols = {c["name"] for c in inspector.get_columns("alerts")}
    assert {"id", "type", "ticker", "analysis_id", "schedule_id", "payload", "read", "created_at"} <= cols
    setting_cols = {c["name"] for c in inspector.get_columns("settings")}
    assert {"key", "value", "encrypted_value", "updated_at"} <= setting_cols
```

기존 `run_migrations_to` 픽스처가 없다면 `test_migrations.py`의 기존 헬퍼 시그니처에 맞춰 동등한 테스트를 작성한다(예: `_upgrade_to("0004")`).

- [ ] **Step 4: 테스트 실행**

Run: `pytest tests/web/test_migrations.py -v`
Expected: 새 테스트 PASS, 기존 0001~0003 테스트도 그대로 통과.

- [ ] **Step 5: 커밋**

```bash
git add migrations/versions/0004_alerts_settings.py tests/web/test_migrations.py
git commit -m "feat(web/m4): add alembic 0004 alerts + settings migration"
```

---

### Task 2: Alert ORM 모델

**Files:**
- Create: `tradingagents_web/models/alert.py`
- Modify: `tradingagents_web/models/__init__.py`
- Test: `tests/web/test_models_alert.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/web/test_models_alert.py
from datetime import datetime, timezone

from tradingagents_web.models import Alert


def test_alert_defaults_and_persistence(db_session):
    row = Alert(
        type="signal_change",
        ticker="AAPL",
        analysis_id=42,
        payload={"prev": "HOLD", "curr": "BUY", "confidence": 0.78},
    )
    db_session.add(row)
    db_session.commit()

    fetched = db_session.query(Alert).one()
    assert fetched.read is False
    assert fetched.payload["curr"] == "BUY"
    assert fetched.created_at.tzinfo is not None
    assert fetched.schedule_id is None


def test_alert_accepts_schedule_failure_shape(db_session):
    row = Alert(
        type="schedule_failed",
        ticker=None,
        schedule_id=7,
        payload={"error": "yfinance HTTPError"},
    )
    db_session.add(row)
    db_session.commit()
    assert db_session.query(Alert).filter_by(type="schedule_failed").count() == 1
```

(`db_session` 픽스처는 `tests/web/conftest.py`에 이미 존재 — 다른 모델 테스트 참고.)

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/web/test_models_alert.py -v`
Expected: ImportError (`Alert` not in models) FAIL.

- [ ] **Step 3: 모델 작성**

```python
# tradingagents_web/models/alert.py
"""Alert ORM: persistent log of signal/run/schedule events the user should see."""
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from tradingagents_web.models.base import Base, utcnow


class Alert(Base):
    """A persisted notification event (in-app + optional Telegram fanout)."""

    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_read_created", "read", "created_at"),
        Index("ix_alerts_ticker", "ticker"),
        Index("ix_alerts_type", "type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # signal_change | run_completed | run_failed | schedule_failed | confidence_change
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    ticker: Mapped[str | None] = mapped_column(String(16), nullable=True)
    analysis_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    schedule_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
```

```python
# tradingagents_web/models/__init__.py — replace contents
"""ORM model exports."""
from tradingagents_web.models.alert import Alert
from tradingagents_web.models.analysis import Analysis
from tradingagents_web.models.base import Base, TimestampMixin
from tradingagents_web.models.holding import Holding
from tradingagents_web.models.schedule import Schedule
from tradingagents_web.models.session import Session
from tradingagents_web.models.setting import Setting
from tradingagents_web.models.user import User

__all__ = [
    "Alert",
    "Analysis",
    "Base",
    "Holding",
    "Schedule",
    "Session",
    "Setting",
    "TimestampMixin",
    "User",
]
```

> 주의: `Setting`은 다음 Task에서 만든다. 잠시 import 에러 방지용으로 이번 단계에서는 `Setting` import 라인을 빼고, Task 3에서 추가한다.

이번 Task 단계의 `__init__.py`는:

```python
"""ORM model exports."""
from tradingagents_web.models.alert import Alert
from tradingagents_web.models.analysis import Analysis
from tradingagents_web.models.base import Base, TimestampMixin
from tradingagents_web.models.holding import Holding
from tradingagents_web.models.schedule import Schedule
from tradingagents_web.models.session import Session
from tradingagents_web.models.user import User

__all__ = [
    "Alert",
    "Analysis",
    "Base",
    "Holding",
    "Schedule",
    "Session",
    "TimestampMixin",
    "User",
]
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/web/test_models_alert.py -v`
Expected: PASS.

- [ ] **Step 5: 커밋**

```bash
git add tradingagents_web/models/alert.py tradingagents_web/models/__init__.py tests/web/test_models_alert.py
git commit -m "feat(web/m4): add Alert ORM model"
```

---

### Task 3: Setting ORM 모델

**Files:**
- Create: `tradingagents_web/models/setting.py`
- Modify: `tradingagents_web/models/__init__.py`
- Test: `tests/web/test_models_setting.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/web/test_models_setting.py
from tradingagents_web.models import Setting


def test_setting_value_only(db_session):
    db_session.add(Setting(key="alerts.signal_change", value="true"))
    db_session.commit()
    s = db_session.get(Setting, "alerts.signal_change")
    assert s.value == "true"
    assert s.encrypted_value is None
    assert s.updated_at.tzinfo is not None


def test_setting_encrypted_only(db_session):
    db_session.add(Setting(key="telegram_bot_token", encrypted_value=b"\x00\x01\x02"))
    db_session.commit()
    s = db_session.get(Setting, "telegram_bot_token")
    assert s.value is None
    assert s.encrypted_value == b"\x00\x01\x02"


def test_setting_primary_key_uniqueness(db_session):
    db_session.add(Setting(key="alerts.signal_change", value="true"))
    db_session.commit()
    db_session.add(Setting(key="alerts.signal_change", value="false"))
    import pytest
    import sqlalchemy.exc

    with pytest.raises(sqlalchemy.exc.IntegrityError):
        db_session.commit()
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/web/test_models_setting.py -v`
Expected: ImportError FAIL.

- [ ] **Step 3: 모델 작성 + __init__ 등록**

```python
# tradingagents_web/models/setting.py
"""Setting ORM: key-value store for user-tunable configuration.

For sensitive values (e.g. Telegram bot token) populate ``encrypted_value`` and
leave ``value`` as None. For plain JSON-text values populate ``value``.
"""
from datetime import datetime

from sqlalchemy import DateTime, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from tradingagents_web.models.base import Base, utcnow


class Setting(Base):
    """A single configuration row addressed by a string key."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_value: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
```

`tradingagents_web/models/__init__.py`에 `from tradingagents_web.models.setting import Setting`과 `__all__`의 `"Setting"` 항목을 Task 2 단계에서 빼두었던 그대로 추가:

```python
"""ORM model exports."""
from tradingagents_web.models.alert import Alert
from tradingagents_web.models.analysis import Analysis
from tradingagents_web.models.base import Base, TimestampMixin
from tradingagents_web.models.holding import Holding
from tradingagents_web.models.schedule import Schedule
from tradingagents_web.models.session import Session
from tradingagents_web.models.setting import Setting
from tradingagents_web.models.user import User

__all__ = [
    "Alert",
    "Analysis",
    "Base",
    "Holding",
    "Schedule",
    "Session",
    "Setting",
    "TimestampMixin",
    "User",
]
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/web/test_models_setting.py tests/web/test_models_alert.py -v`
Expected: 두 파일 모두 PASS.

- [ ] **Step 5: 커밋**

```bash
git add tradingagents_web/models/setting.py tradingagents_web/models/__init__.py tests/web/test_models_setting.py
git commit -m "feat(web/m4): add Setting ORM model"
```

---

### Task 4: Pydantic 스키마 — Alert + NotificationSettings

**Files:**
- Create: `tradingagents_web/schemas/alert.py`
- Create: `tradingagents_web/schemas/notification.py`
- Test: `tests/web/test_schemas_alert.py`, `tests/web/test_schemas_notification.py`

- [ ] **Step 1: 실패하는 alert 스키마 테스트 작성**

```python
# tests/web/test_schemas_alert.py
from datetime import datetime, timezone

from tradingagents_web.schemas.alert import (
    AlertItem,
    AlertListResponse,
    AlertType,
    UnreadCountResponse,
)


def test_alert_item_validates_type():
    item = AlertItem(
        id=1,
        type=AlertType.SIGNAL_CHANGE,
        ticker="AAPL",
        analysis_id=42,
        schedule_id=None,
        payload={"prev": "HOLD", "curr": "BUY"},
        read=False,
        created_at=datetime.now(timezone.utc),
    )
    assert item.type == AlertType.SIGNAL_CHANGE


def test_alert_list_response_pagination_bounds():
    resp = AlertListResponse(items=[], total=0, page=1, page_size=20)
    assert resp.total == 0


def test_unread_count_non_negative():
    assert UnreadCountResponse(unread=3).unread == 3
```

- [ ] **Step 2: 실패하는 notification 스키마 테스트 작성**

```python
# tests/web/test_schemas_notification.py
import pytest
from pydantic import ValidationError

from tradingagents_web.schemas.notification import (
    NotificationSettingsResponse,
    NotificationSettingsUpdate,
    TelegramTestRequest,
)


def test_notification_update_threshold_bounds():
    with pytest.raises(ValidationError):
        NotificationSettingsUpdate(confidence_change_threshold=-0.1)
    with pytest.raises(ValidationError):
        NotificationSettingsUpdate(confidence_change_threshold=1.1)


def test_notification_update_partial_ok():
    upd = NotificationSettingsUpdate(alert_on_signal_change=False)
    assert upd.alert_on_signal_change is False
    assert upd.telegram_chat_id is None  # not provided


def test_response_masks_token_presence():
    resp = NotificationSettingsResponse(
        telegram_bot_token_set=True,
        telegram_chat_id="123",
        alert_on_signal_change=True,
        alert_on_run_completed=False,
        alert_on_run_failed=True,
        alert_on_schedule_failed=True,
        confidence_change_threshold=0.10,
    )
    assert resp.telegram_bot_token_set is True


def test_telegram_test_request_requires_token_or_existing():
    # Either explicit token or rely on stored — both must validate
    TelegramTestRequest()  # uses stored
    TelegramTestRequest(telegram_bot_token="abc:def")
```

- [ ] **Step 3: 실패 확인**

Run: `pytest tests/web/test_schemas_alert.py tests/web/test_schemas_notification.py -v`
Expected: ImportError FAIL.

- [ ] **Step 4: 스키마 작성**

```python
# tradingagents_web/schemas/alert.py
"""Pydantic schemas for the alerts API."""
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AlertType(str, Enum):
    SIGNAL_CHANGE = "signal_change"
    CONFIDENCE_CHANGE = "confidence_change"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    SCHEDULE_FAILED = "schedule_failed"


class AlertItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: AlertType
    ticker: str | None
    analysis_id: int | None
    schedule_id: int | None
    payload: dict[str, Any]
    read: bool
    created_at: datetime


class AlertListResponse(BaseModel):
    items: list[AlertItem]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)


class UnreadCountResponse(BaseModel):
    unread: int = Field(ge=0)
```

```python
# tradingagents_web/schemas/notification.py
"""Pydantic schemas for the notification settings API."""
from pydantic import BaseModel, Field


class NotificationSettingsResponse(BaseModel):
    """Response shape — never includes the raw bot token."""

    telegram_bot_token_set: bool
    telegram_chat_id: str | None
    alert_on_signal_change: bool
    alert_on_run_completed: bool
    alert_on_run_failed: bool
    alert_on_schedule_failed: bool
    confidence_change_threshold: float | None = Field(default=None, ge=0.0, le=1.0)


class NotificationSettingsUpdate(BaseModel):
    """Partial update — every field optional. Token only included when (re)setting."""

    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    alert_on_signal_change: bool | None = None
    alert_on_run_completed: bool | None = None
    alert_on_run_failed: bool | None = None
    alert_on_schedule_failed: bool | None = None
    confidence_change_threshold: float | None = Field(default=None, ge=0.0, le=1.0)


class TelegramTestRequest(BaseModel):
    """Optional one-shot token for testing without persisting."""

    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None


class TelegramTestResponse(BaseModel):
    ok: bool
    bot_username: str | None = None
    error: str | None = None
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `pytest tests/web/test_schemas_alert.py tests/web/test_schemas_notification.py -v`
Expected: PASS.

- [ ] **Step 6: 커밋**

```bash
git add tradingagents_web/schemas/alert.py tradingagents_web/schemas/notification.py tests/web/test_schemas_alert.py tests/web/test_schemas_notification.py
git commit -m "feat(web/m4): add alert + notification pydantic schemas"
```

---

### Task 5: signal_diff 순수 함수

**Files:**
- Create: `tradingagents_web/services/signal_diff.py`
- Test: `tests/web/test_signal_diff.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/web/test_signal_diff.py
from dataclasses import dataclass

from tradingagents_web.services.signal_diff import (
    DiffOutcome,
    diff_for_completion,
)


@dataclass
class _Stub:
    """Minimal stand-in for an Analysis row — only the fields diff cares about."""
    id: int
    ticker: str
    decision: str | None
    confidence: float | None
    error: str | None = None


def _cfg(
    signal=True, completed=False, failed=True, threshold=0.10
):
    return {
        "alert_on_signal_change": signal,
        "alert_on_run_completed": completed,
        "alert_on_run_failed": failed,
        "confidence_change_threshold": threshold,
    }


def test_first_completion_no_prior_no_signal_change():
    curr = _Stub(id=1, ticker="AAPL", decision="BUY", confidence=0.7)
    out = diff_for_completion(curr, prior=None, status="completed", config=_cfg())
    assert "signal_change" not in [o.type for o in out]


def test_first_completion_run_completed_alert_when_enabled():
    curr = _Stub(id=1, ticker="AAPL", decision="BUY", confidence=0.7)
    out = diff_for_completion(
        curr, prior=None, status="completed", config=_cfg(completed=True)
    )
    assert any(o.type == "run_completed" for o in out)


def test_signal_change_emits_signal_change():
    prior = _Stub(id=1, ticker="AAPL", decision="HOLD", confidence=0.6)
    curr = _Stub(id=2, ticker="AAPL", decision="BUY", confidence=0.78)
    out = diff_for_completion(curr, prior=prior, status="completed", config=_cfg())
    types = [o.type for o in out]
    assert "signal_change" in types
    sc = next(o for o in out if o.type == "signal_change")
    assert sc.payload == {
        "prev": "HOLD",
        "curr": "BUY",
        "confidence": 0.78,
        "prev_confidence": 0.6,
    }


def test_same_decision_no_signal_change():
    prior = _Stub(id=1, ticker="AAPL", decision="BUY", confidence=0.7)
    curr = _Stub(id=2, ticker="AAPL", decision="BUY", confidence=0.72)
    out = diff_for_completion(curr, prior=prior, status="completed", config=_cfg())
    assert all(o.type != "signal_change" for o in out)


def test_confidence_change_above_threshold_emits():
    prior = _Stub(id=1, ticker="AAPL", decision="BUY", confidence=0.5)
    curr = _Stub(id=2, ticker="AAPL", decision="BUY", confidence=0.65)
    out = diff_for_completion(curr, prior=prior, status="completed", config=_cfg())
    assert any(o.type == "confidence_change" for o in out)


def test_confidence_change_below_threshold_skipped():
    prior = _Stub(id=1, ticker="AAPL", decision="BUY", confidence=0.5)
    curr = _Stub(id=2, ticker="AAPL", decision="BUY", confidence=0.55)
    out = diff_for_completion(curr, prior=prior, status="completed", config=_cfg())
    assert all(o.type != "confidence_change" for o in out)


def test_failed_status_emits_run_failed():
    curr = _Stub(id=1, ticker="AAPL", decision=None, confidence=None, error="boom")
    out = diff_for_completion(curr, prior=None, status="failed", config=_cfg())
    assert any(o.type == "run_failed" for o in out)
    rf = next(o for o in out if o.type == "run_failed")
    assert rf.payload["error"] == "boom"


def test_threshold_none_disables_confidence_alert():
    prior = _Stub(id=1, ticker="AAPL", decision="BUY", confidence=0.4)
    curr = _Stub(id=2, ticker="AAPL", decision="BUY", confidence=0.9)
    out = diff_for_completion(
        curr, prior=prior, status="completed", config=_cfg(threshold=None)
    )
    assert all(o.type != "confidence_change" for o in out)
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/web/test_signal_diff.py -v`
Expected: ImportError FAIL.

- [ ] **Step 3: 구현 작성**

```python
# tradingagents_web/services/signal_diff.py
"""Pure decision-diffing logic for the alerting pipeline.

This module is intentionally side-effect free: it inspects two analysis rows
(or one + None) plus a small config dict and returns a list of trigger
outcomes. The notifier is responsible for persisting Alert rows and pushing
to Telegram.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol


class _AnalysisLike(Protocol):
    id: int
    ticker: str
    decision: str | None
    confidence: float | None
    error: str | None


@dataclass(frozen=True)
class DiffOutcome:
    """One trigger result — maps 1:1 to an Alert row about to be created."""

    type: str  # signal_change | confidence_change | run_completed | run_failed
    payload: dict[str, Any]


def diff_for_completion(
    current: _AnalysisLike,
    prior: _AnalysisLike | None,
    *,
    status: str,
    config: Mapping[str, Any],
) -> list[DiffOutcome]:
    """Compute alert outcomes for one analysis transitioning to a terminal state.

    Args:
        current: The analysis that just transitioned to terminal status.
        prior: The most recent ``completed`` analysis for the same ticker
            (excluding ``current``), or None if this is the first.
        status: Terminal status of ``current`` — ``"completed"`` or ``"failed"``.
        config: Mapping with keys ``alert_on_signal_change``,
            ``alert_on_run_completed``, ``alert_on_run_failed``,
            ``confidence_change_threshold`` (None disables that check).

    Returns:
        Outcomes in priority order: signal_change first, then confidence_change,
        then run_completed (if enabled) or run_failed.
    """
    outcomes: list[DiffOutcome] = []

    if status == "failed":
        if config.get("alert_on_run_failed", True):
            outcomes.append(
                DiffOutcome(
                    type="run_failed",
                    payload={
                        "ticker": current.ticker,
                        "error": current.error or "unknown",
                    },
                )
            )
        return outcomes

    # status == "completed"
    if prior is not None and current.decision and prior.decision and current.decision != prior.decision:
        if config.get("alert_on_signal_change", True):
            outcomes.append(
                DiffOutcome(
                    type="signal_change",
                    payload={
                        "prev": prior.decision,
                        "curr": current.decision,
                        "confidence": current.confidence,
                        "prev_confidence": prior.confidence,
                    },
                )
            )

    threshold = config.get("confidence_change_threshold")
    if (
        threshold is not None
        and prior is not None
        and current.confidence is not None
        and prior.confidence is not None
    ):
        delta = abs(current.confidence - prior.confidence)
        if delta >= threshold:
            outcomes.append(
                DiffOutcome(
                    type="confidence_change",
                    payload={
                        "prev": prior.confidence,
                        "curr": current.confidence,
                        "delta": current.confidence - prior.confidence,
                    },
                )
            )

    if config.get("alert_on_run_completed", False):
        outcomes.append(
            DiffOutcome(
                type="run_completed",
                payload={
                    "ticker": current.ticker,
                    "decision": current.decision,
                    "confidence": current.confidence,
                },
            )
        )

    return outcomes
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/web/test_signal_diff.py -v`
Expected: 8 PASS.

- [ ] **Step 5: 커밋**

```bash
git add tradingagents_web/services/signal_diff.py tests/web/test_signal_diff.py
git commit -m "feat(web/m4): pure signal_diff function for alert triggers"
```

---

### Task 6: settings_store 헬퍼 (암호화 처리)

**Files:**
- Create: `tradingagents_web/services/settings_store.py`
- Test: `tests/web/test_settings_store.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/web/test_settings_store.py
import os

import pytest
from cryptography.fernet import Fernet

from tradingagents_web.models import Setting
from tradingagents_web.services import settings_store


@pytest.fixture(autouse=True)
def _enc_key(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())


def test_load_notification_defaults_when_empty(db_session):
    cfg = settings_store.load_notification_config(db_session)
    assert cfg["alert_on_signal_change"] is True
    assert cfg["alert_on_run_failed"] is True
    assert cfg["alert_on_run_completed"] is False
    assert cfg["alert_on_schedule_failed"] is True
    assert cfg["confidence_change_threshold"] == pytest.approx(0.10)
    assert cfg["telegram_bot_token"] is None
    assert cfg["telegram_chat_id"] is None
    assert cfg["telegram_bot_token_set"] is False


def test_save_and_round_trip(db_session):
    settings_store.save_notification_config(
        db_session,
        updates={
            "telegram_bot_token": "secret-bot-token",
            "telegram_chat_id": "12345",
            "alert_on_signal_change": False,
            "confidence_change_threshold": 0.25,
        },
    )
    cfg = settings_store.load_notification_config(db_session)
    assert cfg["telegram_bot_token"] == "secret-bot-token"
    assert cfg["telegram_bot_token_set"] is True
    assert cfg["telegram_chat_id"] == "12345"
    assert cfg["alert_on_signal_change"] is False
    assert cfg["confidence_change_threshold"] == pytest.approx(0.25)


def test_token_stored_encrypted_not_plaintext(db_session):
    settings_store.save_notification_config(
        db_session, updates={"telegram_bot_token": "sensitive-token-xyz"}
    )
    row = db_session.get(Setting, "telegram_bot_token")
    assert row.value is None
    assert row.encrypted_value is not None
    assert b"sensitive-token-xyz" not in row.encrypted_value


def test_partial_update_preserves_others(db_session):
    settings_store.save_notification_config(
        db_session, updates={"telegram_chat_id": "111"}
    )
    settings_store.save_notification_config(
        db_session, updates={"alert_on_run_completed": True}
    )
    cfg = settings_store.load_notification_config(db_session)
    assert cfg["telegram_chat_id"] == "111"
    assert cfg["alert_on_run_completed"] is True
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/web/test_settings_store.py -v`
Expected: ImportError FAIL.

- [ ] **Step 3: 구현 작성**

```python
# tradingagents_web/services/settings_store.py
"""Read/write helpers for the Setting key-value table.

The notifier and the settings API both depend on this module — keep it a
single source of truth for which keys exist and which keys are encrypted.
"""
from __future__ import annotations

import json
from typing import Any, Mapping

from sqlalchemy.orm import Session as OrmSession

from tradingagents_web.models import Setting
from tradingagents_web.services.crypto import decrypt_secret, encrypt_secret

# Every notification key the system understands. Adding a new key requires
# updating both this dict (for defaults) and ENCRYPTED_KEYS if sensitive.
NOTIFICATION_DEFAULTS: dict[str, Any] = {
    "telegram_bot_token": None,
    "telegram_chat_id": None,
    "alert_on_signal_change": True,
    "alert_on_run_completed": False,
    "alert_on_run_failed": True,
    "alert_on_schedule_failed": True,
    "confidence_change_threshold": 0.10,
}

ENCRYPTED_KEYS: frozenset[str] = frozenset({"telegram_bot_token"})


def load_notification_config(db: OrmSession) -> dict[str, Any]:
    """Return the merged notification config — defaults overlaid with stored rows."""
    cfg = dict(NOTIFICATION_DEFAULTS)
    rows = db.query(Setting).filter(Setting.key.in_(NOTIFICATION_DEFAULTS.keys())).all()
    for row in rows:
        if row.key in ENCRYPTED_KEYS:
            cfg[row.key] = decrypt_secret(row.encrypted_value) if row.encrypted_value else None
        else:
            cfg[row.key] = json.loads(row.value) if row.value is not None else None
    cfg["telegram_bot_token_set"] = cfg.get("telegram_bot_token") is not None
    return cfg


def save_notification_config(
    db: OrmSession, *, updates: Mapping[str, Any]
) -> None:
    """Apply a partial update to the notification config and commit.

    Unknown keys raise KeyError. None values for non-encrypted keys clear them
    (delete the row); for encrypted keys, an empty string clears as well.
    """
    for key, value in updates.items():
        if key not in NOTIFICATION_DEFAULTS:
            raise KeyError(f"Unknown notification setting: {key!r}")

        row = db.get(Setting, key)
        if key in ENCRYPTED_KEYS:
            if value in (None, ""):
                if row is not None:
                    db.delete(row)
            else:
                cipher = encrypt_secret(str(value))
                if row is None:
                    row = Setting(key=key, encrypted_value=cipher)
                    db.add(row)
                else:
                    row.encrypted_value = cipher
                    row.value = None
        else:
            if value is None:
                if row is not None:
                    db.delete(row)
            else:
                serialized = json.dumps(value)
                if row is None:
                    row = Setting(key=key, value=serialized)
                    db.add(row)
                else:
                    row.value = serialized
                    row.encrypted_value = None
    db.commit()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/web/test_settings_store.py -v`
Expected: 4 PASS.

- [ ] **Step 5: 커밋**

```bash
git add tradingagents_web/services/settings_store.py tests/web/test_settings_store.py
git commit -m "feat(web/m4): settings_store helpers with Fernet token encryption"
```

---

### Task 7: telegram 클라이언트 (httpx)

**Files:**
- Create: `tradingagents_web/services/telegram.py`
- Test: `tests/web/test_telegram_service.py`

- [ ] **Step 1: respx 의존성 확인 (없으면 dev 그룹에 추가)**

Run: `python -c "import respx" 2>&1 || echo NOT_INSTALLED`

`NOT_INSTALLED`이면 `pyproject.toml`의 `[dependency-groups].dev`에 `"respx>=0.21"`을 추가하고 `uv sync --group dev`를 실행한다. 추가 후 같은 커밋에 포함하지 말고 별도 step으로 관리.

(이미 설치되어 있으면 그대로 진행.)

- [ ] **Step 2: 실패하는 테스트 작성**

```python
# tests/web/test_telegram_service.py
import httpx
import pytest
import respx

from tradingagents_web.services import telegram


@pytest.mark.asyncio
async def test_send_message_success():
    with respx.mock(assert_all_called=True) as mock:
        route = mock.post("https://api.telegram.org/botABC:DEF/sendMessage").mock(
            return_value=httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})
        )
        ok = await telegram.send_message(
            bot_token="ABC:DEF", chat_id="123", text="hello"
        )
        assert ok is True
        assert route.called
        sent = route.calls.last.request
        assert b"chat_id=123" in sent.content or b'"chat_id":"123"' in sent.content


@pytest.mark.asyncio
async def test_send_message_returns_false_on_4xx():
    with respx.mock() as mock:
        mock.post("https://api.telegram.org/botX:Y/sendMessage").mock(
            return_value=httpx.Response(401, json={"ok": False, "description": "Unauthorized"})
        )
        ok = await telegram.send_message(bot_token="X:Y", chat_id="1", text="x")
        assert ok is False


@pytest.mark.asyncio
async def test_send_message_returns_false_on_network_error():
    with respx.mock() as mock:
        mock.post("https://api.telegram.org/botX:Y/sendMessage").mock(
            side_effect=httpx.ConnectError("boom")
        )
        ok = await telegram.send_message(bot_token="X:Y", chat_id="1", text="x")
        assert ok is False


@pytest.mark.asyncio
async def test_get_me_success():
    with respx.mock() as mock:
        mock.get("https://api.telegram.org/botABC:DEF/getMe").mock(
            return_value=httpx.Response(200, json={"ok": True, "result": {"username": "trbot"}})
        )
        info = await telegram.get_me("ABC:DEF")
        assert info == {"ok": True, "username": "trbot"}


@pytest.mark.asyncio
async def test_get_me_failure_returns_dict_with_error():
    with respx.mock() as mock:
        mock.get("https://api.telegram.org/botBAD:KEY/getMe").mock(
            return_value=httpx.Response(401, json={"ok": False, "description": "Unauthorized"})
        )
        info = await telegram.get_me("BAD:KEY")
        assert info["ok"] is False
        assert "Unauthorized" in info["error"]
```

- [ ] **Step 3: 실패 확인**

Run: `pytest tests/web/test_telegram_service.py -v`
Expected: ImportError FAIL.

- [ ] **Step 4: 구현 작성**

```python
# tradingagents_web/services/telegram.py
"""Minimal async Telegram Bot API client.

Only what the notifier needs: sendMessage (push) and getMe (token validation).
Calls are short-lived AsyncClient sessions; we do not maintain a pool because
notification volume is low (handful per day) and avoids cross-event-loop
client reuse pitfalls in tests.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org"
DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


async def send_message(
    *, bot_token: str, chat_id: str, text: str, parse_mode: str | None = "Markdown"
) -> bool:
    """POST sendMessage. Returns True on Telegram ``ok=true``, False otherwise.

    Network failures and non-200 responses are logged and swallowed; alerting
    must never raise into the analysis pipeline.
    """
    url = f"{API_BASE}/bot{bot_token}/sendMessage"
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
        if resp.status_code != 200:
            logger.warning("Telegram sendMessage non-200: %s %s", resp.status_code, resp.text[:200])
            return False
        body = resp.json()
        return bool(body.get("ok"))
    except httpx.HTTPError as exc:
        logger.warning("Telegram sendMessage failed: %s", exc)
        return False


async def get_me(bot_token: str) -> dict[str, Any]:
    """GET getMe — verifies a bot token. Always returns a dict.

    Successful response: ``{"ok": True, "username": "<botname>"}``.
    Failure response:    ``{"ok": False, "error": "<reason>"}``.
    """
    url = f"{API_BASE}/bot{bot_token}/getMe"
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            resp = await client.get(url)
        body = resp.json()
        if resp.status_code != 200 or not body.get("ok"):
            return {"ok": False, "error": body.get("description") or f"HTTP {resp.status_code}"}
        return {"ok": True, "username": body.get("result", {}).get("username")}
    except httpx.HTTPError as exc:
        return {"ok": False, "error": str(exc)}
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `pytest tests/web/test_telegram_service.py -v`
Expected: 5 PASS.

- [ ] **Step 6: 커밋**

```bash
git add tradingagents_web/services/telegram.py tests/web/test_telegram_service.py pyproject.toml uv.lock
git commit -m "feat(web/m4): add httpx-based Telegram bot client"
```

(uv.lock는 respx 추가 시에만 포함; respx가 이미 설치되어 있었다면 두 파일은 빠진다.)

---

### Task 8: notifier 디스패처

**Files:**
- Create: `tradingagents_web/services/notifier.py`
- Test: `tests/web/test_notifier.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/web/test_notifier.py
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

import pytest
from cryptography.fernet import Fernet

from tradingagents_web.models import Alert, Analysis
from tradingagents_web.services import notifier, settings_store


@pytest.fixture(autouse=True)
def _enc_key(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())


def _make_analysis(db, *, ticker, decision, confidence, status="completed"):
    row = Analysis(
        run_id=f"r-{ticker}-{decision}-{confidence}",
        ticker=ticker,
        analysis_date=date(2026, 4, 26),
        status=status,
        decision=decision,
        confidence=confidence,
        llm_provider="x",
        llm_deep_model="x",
        llm_quick_model="x",
        debate_rounds=1,
        analysts=["market"],
    )
    if status == "completed":
        row.completed_at = datetime.now(timezone.utc)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.mark.asyncio
async def test_dispatch_first_completion_no_signal_change(db_session, monkeypatch):
    sender = AsyncMock(return_value=True)
    monkeypatch.setattr(notifier, "_send_telegram", sender)

    a = _make_analysis(db_session, ticker="AAPL", decision="BUY", confidence=0.7)
    await notifier.dispatch_for_analysis(
        a.id, session_factory=lambda: db_session
    )

    assert db_session.query(Alert).count() == 0  # no prior, defaults skip run_completed
    sender.assert_not_called()


@pytest.mark.asyncio
async def test_dispatch_signal_change_creates_alert_and_sends_telegram(
    db_session, monkeypatch
):
    sender = AsyncMock(return_value=True)
    monkeypatch.setattr(notifier, "_send_telegram", sender)
    settings_store.save_notification_config(
        db_session,
        updates={"telegram_bot_token": "T:OK", "telegram_chat_id": "9"},
    )

    _make_analysis(db_session, ticker="AAPL", decision="HOLD", confidence=0.5)
    curr = _make_analysis(db_session, ticker="AAPL", decision="BUY", confidence=0.8)

    await notifier.dispatch_for_analysis(
        curr.id, session_factory=lambda: db_session
    )

    rows = db_session.query(Alert).all()
    types = sorted(r.type for r in rows)
    assert "signal_change" in types
    assert "confidence_change" in types  # |0.8 - 0.5| = 0.3 > 0.10
    sender.assert_awaited()  # at least once


@pytest.mark.asyncio
async def test_dispatch_failed_analysis_creates_run_failed_alert(
    db_session, monkeypatch
):
    monkeypatch.setattr(notifier, "_send_telegram", AsyncMock(return_value=True))
    a = _make_analysis(
        db_session, ticker="AAPL", decision=None, confidence=None, status="failed"
    )
    a.error = "yfinance HTTPError"
    db_session.commit()

    await notifier.dispatch_for_analysis(
        a.id, session_factory=lambda: db_session
    )
    row = db_session.query(Alert).filter_by(type="run_failed").one()
    assert row.payload["error"] == "yfinance HTTPError"


@pytest.mark.asyncio
async def test_telegram_skipped_when_token_missing(db_session, monkeypatch):
    sender = AsyncMock(return_value=True)
    monkeypatch.setattr(notifier, "_send_telegram", sender)

    _make_analysis(db_session, ticker="AAPL", decision="HOLD", confidence=0.5)
    curr = _make_analysis(db_session, ticker="AAPL", decision="BUY", confidence=0.55)
    await notifier.dispatch_for_analysis(
        curr.id, session_factory=lambda: db_session
    )

    sender.assert_not_called()
    assert db_session.query(Alert).filter_by(type="signal_change").count() == 1


@pytest.mark.asyncio
async def test_dispatch_schedule_failure_creates_alert(db_session, monkeypatch):
    monkeypatch.setattr(notifier, "_send_telegram", AsyncMock(return_value=True))
    await notifier.dispatch_schedule_failure(
        schedule_id=42,
        ticker="NVDA",
        error="connection refused",
        session_factory=lambda: db_session,
    )
    row = db_session.query(Alert).filter_by(type="schedule_failed").one()
    assert row.schedule_id == 42
    assert row.ticker == "NVDA"
    assert row.payload["error"] == "connection refused"


@pytest.mark.asyncio
async def test_dispatch_swallows_exceptions(db_session, monkeypatch, caplog):
    """Notifier must never raise into the runner."""
    def boom(*a, **kw):
        raise RuntimeError("settings broken")
    monkeypatch.setattr(settings_store, "load_notification_config", boom)

    a = _make_analysis(db_session, ticker="AAPL", decision="BUY", confidence=0.7)
    # Should not raise
    await notifier.dispatch_for_analysis(
        a.id, session_factory=lambda: db_session
    )
    assert any("notifier" in rec.name.lower() or "settings broken" in rec.message
              for rec in caplog.records)
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/web/test_notifier.py -v`
Expected: ImportError FAIL.

- [ ] **Step 3: 구현 작성**

```python
# tradingagents_web/services/notifier.py
"""Alert dispatcher: persist Alert rows + push to enabled channels.

Called from two places:
- ``runs._execute_and_persist`` after a run terminates (success or failure)
- ``auto_runner.trigger_run`` exception handler (schedule failure)

The dispatcher is intentionally exception-safe: any internal failure is
logged and swallowed so the analysis pipeline keeps running.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy import desc
from sqlalchemy.orm import Session as OrmSession

from tradingagents_web.models import Alert, Analysis
from tradingagents_web.services import settings_store, telegram
from tradingagents_web.services.signal_diff import DiffOutcome, diff_for_completion

logger = logging.getLogger(__name__)

# Indirection so tests can monkeypatch.
async def _send_telegram(*, bot_token: str, chat_id: str, text: str) -> bool:
    return await telegram.send_message(bot_token=bot_token, chat_id=chat_id, text=text)


def _format_message(outcome: DiffOutcome, *, ticker: str | None) -> str:
    """Return a Markdown message body for a DiffOutcome / schedule failure."""
    p = outcome.payload
    if outcome.type == "signal_change":
        return (
            f"*Signal change* `{ticker}`\n"
            f"{p['prev']} → *{p['curr']}* (conf {p.get('confidence'):.2f})"
        )
    if outcome.type == "confidence_change":
        return (
            f"*Confidence shift* `{ticker}`\n"
            f"{p['prev']:.2f} → {p['curr']:.2f} (Δ {p['delta']:+.2f})"
        )
    if outcome.type == "run_completed":
        return (
            f"*Analysis complete* `{ticker}`\n"
            f"{p.get('decision')} (conf {p.get('confidence', 0):.2f})"
        )
    if outcome.type == "run_failed":
        return f"*Analysis failed* `{ticker}`\n{p.get('error', '')[:200]}"
    if outcome.type == "schedule_failed":
        return f"*Schedule failed* `{ticker or '?'}`\n{p.get('error', '')[:200]}"
    return f"Alert: {outcome.type}"


async def dispatch_for_analysis(
    analysis_id: int,
    *,
    session_factory: Callable[[], OrmSession],
) -> None:
    """Compute outcomes for a finished Analysis row and dispatch alerts.

    Args:
        analysis_id: PK of the analyses row that just transitioned to a
            terminal status (completed or failed).
        session_factory: Zero-arg callable returning a SQLAlchemy session.
            Tests inject a session bound to the test db.
    """
    try:
        db = session_factory()
        try:
            current = db.get(Analysis, analysis_id)
            if current is None:
                logger.warning("dispatch_for_analysis: id=%s not found", analysis_id)
                return
            if current.status not in ("completed", "failed"):
                return

            prior = (
                db.query(Analysis)
                .filter(
                    Analysis.ticker == current.ticker,
                    Analysis.id != current.id,
                    Analysis.status == "completed",
                )
                .order_by(desc(Analysis.created_at), desc(Analysis.id))
                .first()
            )

            cfg = settings_store.load_notification_config(db)
            outcomes = diff_for_completion(
                current, prior=prior, status=current.status, config=cfg
            )

            await _persist_and_push(
                db,
                outcomes=outcomes,
                ticker=current.ticker,
                analysis_id=current.id,
                schedule_id=current.schedule_id,
                cfg=cfg,
            )
        finally:
            db.close()
    except Exception:  # noqa: BLE001 — never raise into the runner
        logger.exception("notifier.dispatch_for_analysis swallowed exception")


async def dispatch_schedule_failure(
    *,
    schedule_id: int,
    ticker: str | None,
    error: str,
    session_factory: Callable[[], OrmSession],
) -> None:
    """Emit a schedule_failed alert (in-app + telegram if enabled)."""
    try:
        db = session_factory()
        try:
            cfg = settings_store.load_notification_config(db)
            if not cfg.get("alert_on_schedule_failed", True):
                return
            outcome = DiffOutcome(
                type="schedule_failed",
                payload={"error": error, "ticker": ticker},
            )
            await _persist_and_push(
                db,
                outcomes=[outcome],
                ticker=ticker,
                analysis_id=None,
                schedule_id=schedule_id,
                cfg=cfg,
            )
        finally:
            db.close()
    except Exception:  # noqa: BLE001
        logger.exception("notifier.dispatch_schedule_failure swallowed exception")


async def _persist_and_push(
    db: OrmSession,
    *,
    outcomes: list[DiffOutcome],
    ticker: str | None,
    analysis_id: int | None,
    schedule_id: int | None,
    cfg: dict,
) -> None:
    """Insert Alert rows for each outcome and fan out to Telegram if configured."""
    if not outcomes:
        return

    rows: list[Alert] = []
    for o in outcomes:
        row = Alert(
            type=o.type,
            ticker=ticker,
            analysis_id=analysis_id,
            schedule_id=schedule_id,
            payload=o.payload,
            read=False,
            created_at=datetime.now(timezone.utc),
        )
        db.add(row)
        rows.append(row)
    db.commit()

    bot_token = cfg.get("telegram_bot_token")
    chat_id = cfg.get("telegram_chat_id")
    if not bot_token or not chat_id:
        return

    sends = [
        _send_telegram(
            bot_token=bot_token,
            chat_id=chat_id,
            text=_format_message(o, ticker=ticker),
        )
        for o in outcomes
    ]
    # Run concurrently but don't bubble exceptions
    await asyncio.gather(*sends, return_exceptions=True)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/web/test_notifier.py -v`
Expected: 6 PASS.

- [ ] **Step 5: 커밋**

```bash
git add tradingagents_web/services/notifier.py tests/web/test_notifier.py
git commit -m "feat(web/m4): notifier dispatcher persists alerts + pushes telegram"
```

---

### Task 9: runner + auto_runner 통합 — 알림 트리거 연결

**Files:**
- Modify: `tradingagents_web/api/runs.py` (lines around `_execute_and_persist`)
- Modify: `tradingagents_web/services/auto_runner.py`
- Test: `tests/web/test_runs_api.py` (또는 신규 `test_runs_alerts_integration.py`)
- Test: `tests/web/test_auto_runner.py` (실패 분기 추가)

- [ ] **Step 1: 실패하는 통합 테스트 추가 (analysis 완료 → notifier 호출)**

신규 파일 `tests/web/test_runs_alerts_integration.py`:

```python
"""Verify _execute_and_persist invokes notifier on completion and failure."""
from unittest.mock import AsyncMock

import pytest

from tradingagents_web.api import runs as runs_api
from tradingagents_web.services import notifier


@pytest.mark.asyncio
async def test_completion_invokes_notifier(monkeypatch, db_session, fake_runner):
    spy = AsyncMock()
    monkeypatch.setattr(notifier, "dispatch_for_analysis", spy)
    runs_api.set_background_session_factory(lambda: db_session)

    run_id = runs_api.start_analysis_run(
        db_session,
        ticker="AAPL",
        analysis_date=__import__("datetime").date(2026, 4, 26),
        analysts=["market"],
        debate_rounds=1,
        llm_provider="x",
        llm_deep_model="x",
        llm_quick_model="x",
    )
    # Wait for the background task spawned inside start_analysis_run
    await fake_runner.wait_until_done(run_id)
    spy.assert_awaited()  # called at least once
    # The id arg should be the analysis row's PK, not the run_id string
    called_arg = spy.await_args.args[0]
    assert isinstance(called_arg, int)


@pytest.mark.asyncio
async def test_failure_path_invokes_notifier(monkeypatch, db_session, fake_runner):
    spy = AsyncMock()
    monkeypatch.setattr(notifier, "dispatch_for_analysis", spy)
    fake_runner.force_error = True
    runs_api.set_background_session_factory(lambda: db_session)

    run_id = runs_api.start_analysis_run(
        db_session,
        ticker="AAPL",
        analysis_date=__import__("datetime").date(2026, 4, 26),
        analysts=["market"],
        debate_rounds=1,
        llm_provider="x",
        llm_deep_model="x",
        llm_quick_model="x",
    )
    await fake_runner.wait_until_done(run_id)
    spy.assert_awaited()
```

`fake_runner` 픽스처는 기존 `tests/web/conftest.py`에 이미 존재한다고 가정 (M2에서 추가됨). `force_error` 또는 동등한 인터페이스가 없으면 conftest에서 추가해야 한다 — 먼저 grep으로 확인:

Run: `grep -n "fake_runner" tests/web/conftest.py`

존재하지 않거나 force_error가 없으면 다음 단계 전에 conftest를 보강한다. 이미 있다면 다음 단계로.

- [ ] **Step 2: 실패하는 auto_runner 테스트 추가**

`tests/web/test_auto_runner.py`에 추가:

```python
@pytest.mark.asyncio
async def test_trigger_run_dispatches_schedule_failure_on_exception(
    db_session, monkeypatch
):
    from tradingagents_web.services import notifier
    from tradingagents_web.services import auto_runner

    spy = AsyncMock()
    monkeypatch.setattr(notifier, "dispatch_schedule_failure", spy)

    # Make start_analysis_run blow up
    def boom(*a, **kw):
        raise RuntimeError("connection refused")

    from tradingagents_web.api import runs as runs_api
    monkeypatch.setattr(runs_api, "start_analysis_run", boom)

    sched = Schedule(
        name="t", ticker="AAPL", cron_expr="0 9 * * 1-5",
        preset={}, active=True, source="user",
    )
    db_session.add(sched)
    db_session.commit()

    result = await auto_runner.trigger_run(sched.id, session_factory=lambda: db_session)
    assert result is None
    spy.assert_awaited_once()
    kwargs = spy.await_args.kwargs
    assert kwargs["schedule_id"] == sched.id
    assert kwargs["ticker"] == "AAPL"
    assert "connection refused" in kwargs["error"]
```

(`Schedule`, `AsyncMock`, `pytest` import는 파일 상단에 보강.)

- [ ] **Step 3: 실패 확인**

Run: `pytest tests/web/test_runs_alerts_integration.py tests/web/test_auto_runner.py::test_trigger_run_dispatches_schedule_failure_on_exception -v`
Expected: notifier 메서드 호출 안되어 FAIL.

- [ ] **Step 4: runs.py 수정 — `_execute_and_persist`에 dispatch 추가**

`tradingagents_web/api/runs.py`의 `_execute_and_persist` 함수 끝부분과 success/failure 분기에 dispatch 호출을 추가한다. 핵심 변경은 두 군데.

성공 분기:

```python
            row.status = "completed"
            row.decision = result.decision
            row.confidence = result.confidence
            row.final_state = result.final_state
            row.cost_usd = result.cost_usd
            row.completed_at = datetime.now(timezone.utc)
            db.commit()
            row_id = row.id   # <-- capture before notifier opens its own session
        except Exception as exc:  # noqa: BLE001 — record any failure
            ...
```

`finally` 직전, `db.close()` 후에 별도 dispatch:

실제 패치는 함수 전체를 다음으로 교체한다 (현재 `db.close()` 위치를 살리면서 dispatch는 finally 밖, 함수 끝에서 호출):

```python
async def _execute_and_persist(run_id: str, request: RunRequest) -> None:
    """Background task: run the analysis and write the final state to DB.

    Opens a fresh DB session independent of the request-scoped session,
    since the request session is closed before this coroutine completes.

    On terminal status (completed/failed) the alert notifier is invoked with
    the analysis row id. Notifier failures are swallowed inside the notifier
    itself so they cannot break this pipeline.
    """
    from tradingagents_web.services import notifier

    runner = make_runner()
    db = _session_factory()
    analysis_id: int | None = None
    try:
        try:
            result = await runner.run(request)
            row = db.query(Analysis).filter_by(run_id=run_id).one()
            if row.status == "cancelled":
                return  # cancellation wins; don't overwrite
            row.status = "completed"
            row.decision = result.decision
            row.confidence = result.confidence
            row.final_state = result.final_state
            row.cost_usd = result.cost_usd
            row.completed_at = datetime.now(timezone.utc)
            db.commit()
            analysis_id = row.id
        except Exception as exc:  # noqa: BLE001 — record any failure
            logger.exception("Run %s failed", run_id)
            row = db.query(Analysis).filter_by(run_id=run_id).one_or_none()
            if row is not None:
                row.status = "failed"
                row.error = str(exc)[:2000]
                row.completed_at = datetime.now(timezone.utc)
                db.commit()
                analysis_id = row.id
            bus = get_event_bus()
            if not bus.is_finished(run_id):
                bus.publish(
                    run_id,
                    AnalysisEvent(type="error", data={"message": str(exc)}),
                )
                bus.finish(run_id)
    finally:
        db.close()

    if analysis_id is not None:
        await notifier.dispatch_for_analysis(
            analysis_id, session_factory=_session_factory
        )
```

- [ ] **Step 5: auto_runner.py 수정 — 예외 시 schedule_failed 알림**

`tradingagents_web/services/auto_runner.py`의 `trigger_run`을 다음과 같이 try/except로 감싼다:

```python
async def trigger_run(
    schedule_id: int,
    *,
    session_factory: Callable[[], OrmSession] | None = None,
) -> str | None:
    """..."""
    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents_web.api import runs as runs_api
    from tradingagents_web.api.runs import start_analysis_run
    from tradingagents_web.services import notifier

    if session_factory is None:
        session_factory = runs_api._session_factory

    db = session_factory()
    sched_ticker: str | None = None
    try:
        sched = db.query(Schedule).get(schedule_id)
        if sched is None:
            logger.warning("Schedule %s not found at fire time", schedule_id)
            return None
        if not sched.active:
            logger.info("Schedule %s is inactive — skipping fire", schedule_id)
            return None
        sched_ticker = sched.ticker

        preset = sched.preset or {}
        analysts = preset.get("analysts") or [
            "market", "social", "news", "fundamentals",
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
    except Exception as exc:  # noqa: BLE001
        logger.exception("Schedule %s trigger failed", schedule_id)
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        await notifier.dispatch_schedule_failure(
            schedule_id=schedule_id,
            ticker=sched_ticker,
            error=str(exc)[:500],
            session_factory=session_factory,
        )
        return None
    finally:
        db.close()
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `pytest tests/web/test_runs_alerts_integration.py tests/web/test_auto_runner.py tests/web/test_runs_api.py -v`
Expected: 모두 PASS. M2/M3 회귀 없음.

- [ ] **Step 7: 커밋**

```bash
git add tradingagents_web/api/runs.py tradingagents_web/services/auto_runner.py \
        tests/web/test_runs_alerts_integration.py tests/web/test_auto_runner.py
git commit -m "feat(web/m4): wire notifier into runner + scheduler error path"
```

---

### Task 10: Alerts API — list / unread-count / mark read

**Files:**
- Create: `tradingagents_web/api/alerts.py`
- Test: `tests/web/test_alerts_api.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/web/test_alerts_api.py
from datetime import datetime, timezone

from tradingagents_web.models import Alert


def _seed(db, *rows):
    for r in rows:
        db.add(r)
    db.commit()


def _alert(**kw):
    base = dict(
        type="signal_change",
        ticker="AAPL",
        analysis_id=None,
        schedule_id=None,
        payload={},
        read=False,
        created_at=datetime.now(timezone.utc),
    )
    base.update(kw)
    return Alert(**base)


def test_list_alerts_pagination(authed_client, db_session):
    _seed(db_session, *[_alert(ticker=f"T{i}") for i in range(25)])
    r = authed_client.get("/api/alerts?page=1&page_size=10")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 25
    assert len(body["items"]) == 10
    assert body["page"] == 1


def test_list_alerts_filter_by_read(authed_client, db_session):
    _seed(db_session, _alert(read=True), _alert(read=False), _alert(read=False))
    r = authed_client.get("/api/alerts?read=false")
    assert r.status_code == 200
    assert r.json()["total"] == 2


def test_list_alerts_filter_by_type(authed_client, db_session):
    _seed(db_session, _alert(type="signal_change"), _alert(type="run_failed"))
    r = authed_client.get("/api/alerts?type=run_failed")
    assert r.status_code == 200
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["type"] == "run_failed"


def test_unread_count(authed_client, db_session):
    _seed(db_session, _alert(read=True), _alert(read=False), _alert(read=False))
    r = authed_client.get("/api/alerts/unread-count")
    assert r.status_code == 200
    assert r.json() == {"unread": 2}


def test_mark_read(authed_client, db_session):
    a = _alert()
    _seed(db_session, a)
    r = authed_client.post(
        f"/api/alerts/{a.id}/read", headers={"X-Requested-With": "XMLHttpRequest"}
    )
    assert r.status_code == 200
    db_session.refresh(a)
    assert a.read is True


def test_mark_read_404(authed_client):
    r = authed_client.post(
        "/api/alerts/999999/read", headers={"X-Requested-With": "XMLHttpRequest"}
    )
    assert r.status_code == 404


def test_mark_all_read(authed_client, db_session):
    _seed(db_session, _alert(read=False), _alert(read=False), _alert(read=True))
    r = authed_client.post(
        "/api/alerts/read-all", headers={"X-Requested-With": "XMLHttpRequest"}
    )
    assert r.status_code == 200
    assert r.json() == {"marked": 2}
    assert db_session.query(Alert).filter_by(read=False).count() == 0


def test_alerts_require_auth(client):
    r = client.get("/api/alerts")
    assert r.status_code == 401
```

(`authed_client`, `client`는 기존 conftest에 있음.)

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/web/test_alerts_api.py -v`
Expected: 라우터 미등록 → 404 FAIL.

- [ ] **Step 3: 라우터 작성**

```python
# tradingagents_web/api/alerts.py
"""Alerts API: list, unread count, mark read, mark-all-read."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select, update
from sqlalchemy.orm import Session as OrmSession

from tradingagents_web.auth import get_current_user, require_xhr
from tradingagents_web.db import get_db
from tradingagents_web.models import Alert, User
from tradingagents_web.schemas.alert import (
    AlertItem,
    AlertListResponse,
    AlertType,
    UnreadCountResponse,
)

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=AlertListResponse)
def list_alerts(
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    type_: Annotated[AlertType | None, Query(alias="type")] = None,
    ticker: str | None = None,
    read: bool | None = None,
    page: int = 1,
    page_size: int = 20,
) -> AlertListResponse:
    page = max(1, page)
    page_size = max(1, min(100, page_size))

    filters = []
    if type_ is not None:
        filters.append(Alert.type == type_.value)
    if ticker:
        filters.append(Alert.ticker == ticker.strip().upper())
    if read is not None:
        filters.append(Alert.read == read)

    base = select(Alert)
    if filters:
        base = base.where(*filters)

    total_stmt = select(func.count()).select_from(Alert)
    if filters:
        total_stmt = total_stmt.where(*filters)
    total = db.execute(total_stmt).scalar_one()

    rows = (
        db.execute(
            base.order_by(desc(Alert.created_at), desc(Alert.id))
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        .scalars()
        .all()
    )
    return AlertListResponse(
        items=[AlertItem.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
def unread_count(
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> UnreadCountResponse:
    count = db.execute(
        select(func.count()).select_from(Alert).where(Alert.read == False)  # noqa: E712
    ).scalar_one()
    return UnreadCountResponse(unread=count)


@router.post("/{alert_id}/read")
def mark_read(
    alert_id: int,
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> dict[str, bool]:
    row = db.get(Alert, alert_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    row.read = True
    db.commit()
    return {"ok": True}


@router.post("/read-all")
def mark_all_read(
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> dict[str, int]:
    result = db.execute(
        update(Alert).where(Alert.read == False).values(read=True)  # noqa: E712
    )
    db.commit()
    return {"marked": result.rowcount or 0}
```

`tradingagents_web/main.py`에 라우터 등록 (Task 12에서 일괄 처리).

- [ ] **Step 4: 임시 라우터 등록 후 테스트 실행**

`tradingagents_web/main.py`에서 `from tradingagents_web.api import alerts as alerts_api` 추가하고 `app.include_router(alerts_api.router)` 호출 추가.

Run: `pytest tests/web/test_alerts_api.py -v`
Expected: 8 PASS.

- [ ] **Step 5: 커밋**

```bash
git add tradingagents_web/api/alerts.py tradingagents_web/main.py tests/web/test_alerts_api.py
git commit -m "feat(web/m4): alerts API (list, unread-count, mark-read)"
```

---

### Task 11: Notifications Settings API

**Files:**
- Create: `tradingagents_web/api/settings_notifications.py`
- Test: `tests/web/test_settings_notifications_api.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/web/test_settings_notifications_api.py
from unittest.mock import AsyncMock

import pytest
from cryptography.fernet import Fernet


@pytest.fixture(autouse=True)
def _enc_key(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())


def test_get_defaults(authed_client):
    r = authed_client.get("/api/settings/notifications")
    assert r.status_code == 200
    body = r.json()
    assert body["telegram_bot_token_set"] is False
    assert body["telegram_chat_id"] is None
    assert body["alert_on_signal_change"] is True
    assert body["alert_on_run_completed"] is False
    assert body["confidence_change_threshold"] == 0.10


def test_put_update_partial_and_get(authed_client):
    r = authed_client.put(
        "/api/settings/notifications",
        json={"telegram_bot_token": "abc:DEF", "telegram_chat_id": "999"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["telegram_bot_token_set"] is True
    assert body["telegram_chat_id"] == "999"
    # Token never echoed back
    assert "telegram_bot_token" not in body or body.get("telegram_bot_token") in (None, "***")


def test_put_validates_threshold(authed_client):
    r = authed_client.put(
        "/api/settings/notifications",
        json={"confidence_change_threshold": 5},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert r.status_code == 422


def test_test_telegram_with_inline_token(authed_client, monkeypatch):
    from tradingagents_web.api import settings_notifications as api

    async def fake_get_me(token):
        assert token == "T:123"
        return {"ok": True, "username": "trbot"}

    monkeypatch.setattr(api.telegram, "get_me", fake_get_me)
    monkeypatch.setattr(api.telegram, "send_message", AsyncMock(return_value=True))

    r = authed_client.post(
        "/api/settings/notifications/test",
        json={"telegram_bot_token": "T:123", "telegram_chat_id": "9"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True, "bot_username": "trbot", "error": None}


def test_test_telegram_with_stored_token(authed_client, monkeypatch):
    # Save first, then call test without token — should use stored
    authed_client.put(
        "/api/settings/notifications",
        json={"telegram_bot_token": "STORED:tok", "telegram_chat_id": "1"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    from tradingagents_web.api import settings_notifications as api

    async def fake_get_me(token):
        assert token == "STORED:tok"
        return {"ok": True, "username": "ok"}

    monkeypatch.setattr(api.telegram, "get_me", fake_get_me)
    monkeypatch.setattr(api.telegram, "send_message", AsyncMock(return_value=True))

    r = authed_client.post(
        "/api/settings/notifications/test",
        json={},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_test_telegram_no_token_returns_422(authed_client):
    r = authed_client.post(
        "/api/settings/notifications/test",
        json={},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert r.status_code == 422


def test_settings_require_auth(client):
    r = client.get("/api/settings/notifications")
    assert r.status_code == 401
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/web/test_settings_notifications_api.py -v`
Expected: 라우터 미등록 → 404 FAIL.

- [ ] **Step 3: 라우터 작성**

```python
# tradingagents_web/api/settings_notifications.py
"""Notification settings API: GET/PUT current config + POST test."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as OrmSession

from tradingagents_web.auth import get_current_user, require_xhr
from tradingagents_web.db import get_db
from tradingagents_web.models import User
from tradingagents_web.schemas.notification import (
    NotificationSettingsResponse,
    NotificationSettingsUpdate,
    TelegramTestRequest,
    TelegramTestResponse,
)
from tradingagents_web.services import settings_store, telegram

router = APIRouter(prefix="/api/settings/notifications", tags=["settings"])


def _to_response(cfg: dict) -> NotificationSettingsResponse:
    return NotificationSettingsResponse(
        telegram_bot_token_set=cfg["telegram_bot_token_set"],
        telegram_chat_id=cfg["telegram_chat_id"],
        alert_on_signal_change=cfg["alert_on_signal_change"],
        alert_on_run_completed=cfg["alert_on_run_completed"],
        alert_on_run_failed=cfg["alert_on_run_failed"],
        alert_on_schedule_failed=cfg["alert_on_schedule_failed"],
        confidence_change_threshold=cfg["confidence_change_threshold"],
    )


@router.get("", response_model=NotificationSettingsResponse)
def get_notifications(
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> NotificationSettingsResponse:
    cfg = settings_store.load_notification_config(db)
    return _to_response(cfg)


@router.put("", response_model=NotificationSettingsResponse)
def update_notifications(
    payload: NotificationSettingsUpdate,
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> NotificationSettingsResponse:
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    settings_store.save_notification_config(db, updates=updates)
    return _to_response(settings_store.load_notification_config(db))


@router.post("/test", response_model=TelegramTestResponse)
async def test_telegram(
    payload: TelegramTestRequest,
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> TelegramTestResponse:
    cfg = settings_store.load_notification_config(db)
    token = payload.telegram_bot_token or cfg.get("telegram_bot_token")
    chat_id = payload.telegram_chat_id or cfg.get("telegram_chat_id")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No Telegram bot token configured",
        )
    info = await telegram.get_me(token)
    if not info.get("ok"):
        return TelegramTestResponse(ok=False, error=info.get("error", "unknown"))
    if chat_id:
        sent = await telegram.send_message(
            bot_token=token, chat_id=chat_id, text="✅ TradingAgents test message"
        )
        if not sent:
            return TelegramTestResponse(
                ok=False, bot_username=info.get("username"), error="sendMessage failed"
            )
    return TelegramTestResponse(ok=True, bot_username=info.get("username"))
```

- [ ] **Step 4: 임시 라우터 등록 후 테스트 실행**

`tradingagents_web/main.py`에서 `from tradingagents_web.api import settings_notifications as settings_notifications_api`와 `app.include_router(settings_notifications_api.router)` 추가.

Run: `pytest tests/web/test_settings_notifications_api.py -v`
Expected: 7 PASS.

- [ ] **Step 5: 커밋**

```bash
git add tradingagents_web/api/settings_notifications.py tradingagents_web/main.py tests/web/test_settings_notifications_api.py
git commit -m "feat(web/m4): notification settings API + telegram test endpoint"
```

---

### Task 12: main.py 라우터 등록 정리 + lifespan 무영향 확인

이미 Task 10/11에서 라우터를 추가했지만 import 정리가 필요할 수 있다.

**Files:**
- Modify: `tradingagents_web/main.py`

- [ ] **Step 1: main.py 정리**

라우터 import와 등록을 알파벳 정렬 + 그룹 정리:

```python
from tradingagents_web.api import alerts as alerts_api
from tradingagents_web.api import auth as auth_api
from tradingagents_web.api import health
from tradingagents_web.api import holdings as holdings_api
from tradingagents_web.api import prices as prices_api
from tradingagents_web.api import runs as runs_api
from tradingagents_web.api import schedules as schedules_api
from tradingagents_web.api import settings_notifications as settings_notifications_api
```

```python
    app.include_router(health.router)
    app.include_router(auth_api.router)
    app.include_router(runs_api.router)
    app.include_router(holdings_api.router)
    app.include_router(schedules_api.router)
    app.include_router(prices_api.router)
    app.include_router(alerts_api.router)
    app.include_router(settings_notifications_api.router)
```

- [ ] **Step 2: 부팅 회귀 테스트**

Run: `pytest tests/web/test_lifespan.py tests/web/test_health.py -v`
Expected: PASS.

- [ ] **Step 3: 커밋 (있다면)**

```bash
git diff --quiet tradingagents_web/main.py || (git add tradingagents_web/main.py && git commit -m "chore(web/m4): tidy main.py router registration order")
```

---

### Task 13: Frontend `lib/alerts.ts` + 타입

**Files:**
- Create: `web/lib/alerts.ts`
- Create: `web/lib/notification-settings.ts`

- [ ] **Step 1: 타입 + fetch 래퍼 작성**

```typescript
// web/lib/alerts.ts
import { api } from "@/lib/api";

export type AlertType =
  | "signal_change"
  | "confidence_change"
  | "run_completed"
  | "run_failed"
  | "schedule_failed";

export type Alert = {
  id: number;
  type: AlertType;
  ticker: string | null;
  analysis_id: number | null;
  schedule_id: number | null;
  payload: Record<string, unknown>;
  read: boolean;
  created_at: string;
};

export type AlertListResponse = {
  items: Alert[];
  total: number;
  page: number;
  page_size: number;
};

export type AlertFilter = {
  type?: AlertType;
  ticker?: string;
  read?: boolean;
  page?: number;
  page_size?: number;
};

export async function listAlerts(filter: AlertFilter = {}): Promise<AlertListResponse> {
  const params = new URLSearchParams();
  if (filter.type) params.set("type", filter.type);
  if (filter.ticker) params.set("ticker", filter.ticker);
  if (filter.read !== undefined) params.set("read", String(filter.read));
  params.set("page", String(filter.page ?? 1));
  params.set("page_size", String(filter.page_size ?? 20));
  return api(`/api/alerts?${params.toString()}`);
}

export async function fetchUnreadCount(): Promise<{ unread: number }> {
  return api(`/api/alerts/unread-count`);
}

export async function markAlertRead(id: number): Promise<void> {
  await api(`/api/alerts/${id}/read`, { method: "POST" });
}

export async function markAllAlertsRead(): Promise<{ marked: number }> {
  return api(`/api/alerts/read-all`, { method: "POST" });
}
```

```typescript
// web/lib/notification-settings.ts
import { api } from "@/lib/api";

export type NotificationSettings = {
  telegram_bot_token_set: boolean;
  telegram_chat_id: string | null;
  alert_on_signal_change: boolean;
  alert_on_run_completed: boolean;
  alert_on_run_failed: boolean;
  alert_on_schedule_failed: boolean;
  confidence_change_threshold: number | null;
};

export type NotificationSettingsUpdate = Partial<{
  telegram_bot_token: string;
  telegram_chat_id: string;
  alert_on_signal_change: boolean;
  alert_on_run_completed: boolean;
  alert_on_run_failed: boolean;
  alert_on_schedule_failed: boolean;
  confidence_change_threshold: number;
}>;

export type TelegramTestResponse = {
  ok: boolean;
  bot_username: string | null;
  error: string | null;
};

export async function fetchNotificationSettings(): Promise<NotificationSettings> {
  return api(`/api/settings/notifications`);
}

export async function updateNotificationSettings(
  patch: NotificationSettingsUpdate,
): Promise<NotificationSettings> {
  return api(`/api/settings/notifications`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
}

export async function testTelegram(payload: {
  telegram_bot_token?: string;
  telegram_chat_id?: string;
}): Promise<TelegramTestResponse> {
  return api(`/api/settings/notifications/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
```

- [ ] **Step 2: 타입 체크**

Run: `cd web && npx tsc --noEmit`
Expected: 에러 없음.

- [ ] **Step 3: 커밋**

```bash
git add web/lib/alerts.ts web/lib/notification-settings.ts
git commit -m "feat(web/m4): frontend alert + notification settings client"
```

---

### Task 14: Frontend hooks

**Files:**
- Create: `web/hooks/use-alerts.ts`
- Create: `web/hooks/use-unread-count.ts`
- Create: `web/hooks/use-notification-settings.ts`

- [ ] **Step 1: hook 작성**

```typescript
// web/hooks/use-alerts.ts
"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertFilter,
  AlertListResponse,
  listAlerts,
  markAlertRead,
  markAllAlertsRead,
} from "@/lib/alerts";

export function useAlerts(filter: AlertFilter) {
  return useQuery<AlertListResponse>({
    queryKey: ["alerts", filter],
    queryFn: () => listAlerts(filter),
    staleTime: 10_000,
  });
}

export function useMarkAlertRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => markAlertRead(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["alerts"] });
      qc.invalidateQueries({ queryKey: ["alerts", "unread"] });
    },
  });
}

export function useMarkAllAlertsRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => markAllAlertsRead(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["alerts"] });
      qc.invalidateQueries({ queryKey: ["alerts", "unread"] });
    },
  });
}
```

```typescript
// web/hooks/use-unread-count.ts
"use client";
import { useQuery } from "@tanstack/react-query";
import { fetchUnreadCount } from "@/lib/alerts";

export function useUnreadCount() {
  return useQuery({
    queryKey: ["alerts", "unread"],
    queryFn: fetchUnreadCount,
    refetchInterval: 30_000,
    staleTime: 15_000,
  });
}
```

```typescript
// web/hooks/use-notification-settings.ts
"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchNotificationSettings,
  NotificationSettings,
  NotificationSettingsUpdate,
  testTelegram,
  updateNotificationSettings,
} from "@/lib/notification-settings";

export function useNotificationSettings() {
  return useQuery<NotificationSettings>({
    queryKey: ["settings", "notifications"],
    queryFn: fetchNotificationSettings,
  });
}

export function useUpdateNotificationSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: NotificationSettingsUpdate) => updateNotificationSettings(patch),
    onSuccess: (data) => {
      qc.setQueryData(["settings", "notifications"], data);
    },
  });
}

export function useTestTelegram() {
  return useMutation({
    mutationFn: (payload: { telegram_bot_token?: string; telegram_chat_id?: string }) =>
      testTelegram(payload),
  });
}
```

- [ ] **Step 2: 타입 체크**

Run: `cd web && npx tsc --noEmit`
Expected: 에러 없음.

- [ ] **Step 3: 커밋**

```bash
git add web/hooks/use-alerts.ts web/hooks/use-unread-count.ts web/hooks/use-notification-settings.ts
git commit -m "feat(web/m4): TanStack Query hooks for alerts + notification settings"
```

---

### Task 15: Frontend `/alerts` 페이지

**Files:**
- Create: `web/components/alerts/alert-row.tsx`
- Create: `web/components/alerts/alerts-filter-bar.tsx`
- Create: `web/app/(workspace)/alerts/page.tsx`

- [ ] **Step 1: AlertRow 컴포넌트**

```tsx
// web/components/alerts/alert-row.tsx
"use client";
import Link from "next/link";
import { Alert } from "@/lib/alerts";
import { cn } from "@/lib/utils";
import { SignalBadge } from "@/components/shared/signal-badge";

const TYPE_LABEL: Record<Alert["type"], string> = {
  signal_change: "Signal change",
  confidence_change: "Confidence shift",
  run_completed: "Run complete",
  run_failed: "Run failed",
  schedule_failed: "Schedule failed",
};

const TYPE_TONE: Record<Alert["type"], string> = {
  signal_change: "text-accent",
  confidence_change: "text-warn",
  run_completed: "text-text-2",
  run_failed: "text-neg",
  schedule_failed: "text-neg",
};

export function AlertRow({
  alert,
  onMarkRead,
}: {
  alert: Alert;
  onMarkRead: (id: number) => void;
}) {
  const summary = renderSummary(alert);
  return (
    <li
      className={cn(
        "border border-border-1 bg-bg-1 rounded-md p-3 flex items-start gap-3",
        !alert.read && "border-l-2 border-l-accent",
      )}
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest">
          <span className={cn(TYPE_TONE[alert.type])}>{TYPE_LABEL[alert.type]}</span>
          {alert.ticker && (
            <span className="font-mono text-text-2">{alert.ticker}</span>
          )}
          <span className="text-text-3">
            {new Date(alert.created_at).toLocaleString()}
          </span>
        </div>
        <div className="mt-1 text-sm text-text-1">{summary}</div>
        {alert.analysis_id && (
          <Link
            href={`/history/${alert.analysis_id}`}
            className="text-xs text-text-2 underline-offset-2 hover:underline mt-1 inline-block"
          >
            Open analysis →
          </Link>
        )}
      </div>
      {!alert.read && (
        <button
          onClick={() => onMarkRead(alert.id)}
          className="text-xs text-text-2 hover:text-text-1"
        >
          Mark read
        </button>
      )}
    </li>
  );
}

function renderSummary(alert: Alert): React.ReactNode {
  const p = alert.payload as Record<string, unknown>;
  if (alert.type === "signal_change") {
    return (
      <span className="flex items-center gap-1">
        <SignalBadge value={String(p.prev)} />
        <span>→</span>
        <SignalBadge value={String(p.curr)} />
        <span className="text-text-3 ml-1">
          conf {Number(p.confidence ?? 0).toFixed(2)}
        </span>
      </span>
    );
  }
  if (alert.type === "confidence_change") {
    return (
      <span className="font-mono text-text-2">
        {Number(p.prev).toFixed(2)} → {Number(p.curr).toFixed(2)} (Δ
        {Number(p.delta) >= 0 ? "+" : ""}
        {Number(p.delta).toFixed(2)})
      </span>
    );
  }
  if (alert.type === "run_completed") {
    return (
      <span>
        <SignalBadge value={String(p.decision ?? "")} />
        <span className="text-text-3 ml-2">
          conf {Number(p.confidence ?? 0).toFixed(2)}
        </span>
      </span>
    );
  }
  if (alert.type === "run_failed" || alert.type === "schedule_failed") {
    return <span className="text-neg">{String(p.error ?? "unknown error")}</span>;
  }
  return null;
}
```

- [ ] **Step 2: 필터 바**

```tsx
// web/components/alerts/alerts-filter-bar.tsx
"use client";
import { AlertType } from "@/lib/alerts";
import { cn } from "@/lib/utils";

const TYPES: { value: AlertType | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "signal_change", label: "Signal" },
  { value: "confidence_change", label: "Confidence" },
  { value: "run_completed", label: "Completed" },
  { value: "run_failed", label: "Run failed" },
  { value: "schedule_failed", label: "Schedule failed" },
];

export function AlertsFilterBar({
  type,
  unreadOnly,
  onChangeType,
  onToggleUnread,
}: {
  type: AlertType | "all";
  unreadOnly: boolean;
  onChangeType: (t: AlertType | "all") => void;
  onToggleUnread: (v: boolean) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="flex flex-wrap gap-1">
        {TYPES.map((t) => (
          <button
            key={t.value}
            onClick={() => onChangeType(t.value)}
            className={cn(
              "rounded-md px-2 py-1 text-xs border",
              type === t.value
                ? "bg-bg-2 border-border-2 text-text-1"
                : "bg-bg-1 border-border-1 text-text-2 hover:text-text-1",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>
      <label className="ml-auto flex items-center gap-2 text-xs text-text-2">
        <input
          type="checkbox"
          checked={unreadOnly}
          onChange={(e) => onToggleUnread(e.target.checked)}
        />
        Unread only
      </label>
    </div>
  );
}
```

- [ ] **Step 3: 페이지**

```tsx
// web/app/(workspace)/alerts/page.tsx
"use client";
import { useState } from "react";
import { AlertsFilterBar } from "@/components/alerts/alerts-filter-bar";
import { AlertRow } from "@/components/alerts/alert-row";
import { useAlerts, useMarkAlertRead, useMarkAllAlertsRead } from "@/hooks/use-alerts";
import { AlertType } from "@/lib/alerts";

export default function AlertsPage() {
  const [type, setType] = useState<AlertType | "all">("all");
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [page, setPage] = useState(1);

  const filter = {
    page,
    page_size: 20,
    ...(type !== "all" ? { type } : {}),
    ...(unreadOnly ? { read: false } : {}),
  };
  const { data, isLoading } = useAlerts(filter);
  const markRead = useMarkAlertRead();
  const markAll = useMarkAllAlertsRead();

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between">
        <h1 className="text-lg text-text-1">Alerts</h1>
        <button
          onClick={() => markAll.mutate()}
          disabled={markAll.isPending || (data?.total ?? 0) === 0}
          className="text-xs text-text-2 hover:text-text-1 disabled:opacity-40"
        >
          Mark all read
        </button>
      </header>
      <AlertsFilterBar
        type={type}
        unreadOnly={unreadOnly}
        onChangeType={(t) => {
          setType(t);
          setPage(1);
        }}
        onToggleUnread={(v) => {
          setUnreadOnly(v);
          setPage(1);
        }}
      />
      {isLoading ? (
        <div className="text-text-3 text-sm">Loading…</div>
      ) : data && data.items.length > 0 ? (
        <ul className="space-y-2">
          {data.items.map((a) => (
            <AlertRow key={a.id} alert={a} onMarkRead={(id) => markRead.mutate(id)} />
          ))}
        </ul>
      ) : (
        <div className="text-text-3 text-sm">No alerts.</div>
      )}
      {data && data.total > data.page_size && (
        <div className="flex items-center gap-2 text-xs text-text-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="rounded-md border border-border-1 px-2 py-1 disabled:opacity-40"
          >
            Prev
          </button>
          <span>
            Page {data.page} of {Math.ceil(data.total / data.page_size)}
          </span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={page * data.page_size >= data.total}
            className="rounded-md border border-border-1 px-2 py-1 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: 타입 체크 + 빌드**

Run: `cd web && npx tsc --noEmit && npm run build`
Expected: 빌드 성공. 사이드바의 `/alerts` 링크가 이제 동작.

- [ ] **Step 5: 커밋**

```bash
git add web/components/alerts/ web/app/\(workspace\)/alerts/
git commit -m "feat(web/m4): /alerts page with filter, pagination, mark-read"
```

---

### Task 16: 헤더 벨 아이콘 (UnreadBell) + 워크스페이스 레이아웃 통합

**Files:**
- Create: `web/components/alerts/unread-bell.tsx`
- Modify: `web/app/(workspace)/layout.tsx`

- [ ] **Step 1: UnreadBell 컴포넌트**

```tsx
// web/components/alerts/unread-bell.tsx
"use client";
import Link from "next/link";
import { useUnreadCount } from "@/hooks/use-unread-count";

export function UnreadBell() {
  const { data } = useUnreadCount();
  const count = data?.unread ?? 0;
  return (
    <Link
      href="/alerts"
      aria-label={`Alerts (${count} unread)`}
      className="relative inline-flex h-8 w-8 items-center justify-center rounded-md border border-border-1 bg-bg-1 text-text-2 hover:text-text-1"
    >
      <span aria-hidden>⚑</span>
      {count > 0 && (
        <span className="absolute -top-1 -right-1 min-w-[16px] h-4 px-1 rounded-full bg-accent text-[10px] leading-4 text-white text-center font-mono">
          {count > 99 ? "99+" : count}
        </span>
      )}
    </Link>
  );
}
```

- [ ] **Step 2: 워크스페이스 레이아웃에 추가**

`web/app/(workspace)/layout.tsx`를 읽어 현재 구조를 파악한 뒤, 데스크톱 헤더(존재한다면) 또는 메인 컨텐츠 영역의 우상단 슬롯에 `<UnreadBell />`을 삽입한다. 만약 layout에 헤더가 없다면 다음과 같이 추가:

```tsx
import { UnreadBell } from "@/components/alerts/unread-bell";

// 메인 영역의 children 위에:
<header className="hidden md:flex items-center justify-end px-6 py-2 border-b border-border-1 bg-bg-0">
  <UnreadBell />
</header>
```

기존 layout 구조에 맞춰 자연스러운 위치를 고른다. 모바일은 tab-bar에 이미 Alerts 항목이 있으므로 추가 조치 불필요.

- [ ] **Step 3: 빌드**

Run: `cd web && npx tsc --noEmit && npm run build`
Expected: 성공.

- [ ] **Step 4: 커밋**

```bash
git add web/components/alerts/unread-bell.tsx web/app/\(workspace\)/layout.tsx
git commit -m "feat(web/m4): unread alerts bell in workspace header"
```

---

### Task 17: Frontend `/settings/notifications` 페이지

**Files:**
- Create: `web/app/(workspace)/settings/layout.tsx`
- Create: `web/app/(workspace)/settings/notifications/page.tsx`
- Create: `web/components/settings/notifications-form.tsx`
- Modify: `web/components/nav/sidebar.tsx` (Settings 링크를 `/settings/notifications`로)

- [ ] **Step 1: settings 서브내비 레이아웃**

```tsx
// web/app/(workspace)/settings/layout.tsx
import Link from "next/link";

export default function SettingsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col md:flex-row gap-6">
      <aside className="md:w-48 shrink-0">
        <ul className="flex md:flex-col gap-1 text-sm">
          <li>
            <Link
              href="/settings/notifications"
              className="block rounded-md px-2 py-1.5 text-text-2 hover:bg-bg-2 hover:text-text-1"
            >
              Notifications
            </Link>
          </li>
          {/* LLM/Data/Account 추가는 M5 */}
        </ul>
      </aside>
      <section className="flex-1 min-w-0">{children}</section>
    </div>
  );
}
```

- [ ] **Step 2: NotificationsForm 컴포넌트**

```tsx
// web/components/settings/notifications-form.tsx
"use client";
import { useEffect, useState } from "react";
import {
  useNotificationSettings,
  useTestTelegram,
  useUpdateNotificationSettings,
} from "@/hooks/use-notification-settings";

export function NotificationsForm() {
  const { data, isLoading } = useNotificationSettings();
  const update = useUpdateNotificationSettings();
  const test = useTestTelegram();

  const [token, setToken] = useState("");
  const [chatId, setChatId] = useState("");
  const [signalChange, setSignalChange] = useState(true);
  const [runCompleted, setRunCompleted] = useState(false);
  const [runFailed, setRunFailed] = useState(true);
  const [scheduleFailed, setScheduleFailed] = useState(true);
  const [threshold, setThreshold] = useState("0.10");

  useEffect(() => {
    if (!data) return;
    setChatId(data.telegram_chat_id ?? "");
    setSignalChange(data.alert_on_signal_change);
    setRunCompleted(data.alert_on_run_completed);
    setRunFailed(data.alert_on_run_failed);
    setScheduleFailed(data.alert_on_schedule_failed);
    setThreshold(String(data.confidence_change_threshold ?? 0.1));
  }, [data]);

  if (isLoading || !data) return <div className="text-text-3 text-sm">Loading…</div>;

  function handleSave(e: React.FormEvent) {
    e.preventDefault();
    update.mutate({
      ...(token ? { telegram_bot_token: token } : {}),
      telegram_chat_id: chatId || "",
      alert_on_signal_change: signalChange,
      alert_on_run_completed: runCompleted,
      alert_on_run_failed: runFailed,
      alert_on_schedule_failed: scheduleFailed,
      confidence_change_threshold: Number(threshold),
    });
    setToken("");
  }

  return (
    <form className="space-y-6 max-w-xl" onSubmit={handleSave}>
      <fieldset className="space-y-3">
        <legend className="text-xs uppercase tracking-widest text-text-3">
          Telegram
        </legend>
        <label className="block text-xs text-text-2">
          Bot token
          <input
            type="password"
            placeholder={data.telegram_bot_token_set ? "•••••• (saved)" : "123:abc..."}
            value={token}
            onChange={(e) => setToken(e.target.value)}
            className="mt-1 w-full rounded-md border border-border-1 bg-bg-1 px-2 py-1.5 font-mono text-sm text-text-1"
          />
        </label>
        <label className="block text-xs text-text-2">
          Chat ID
          <input
            value={chatId}
            onChange={(e) => setChatId(e.target.value)}
            className="mt-1 w-full rounded-md border border-border-1 bg-bg-1 px-2 py-1.5 font-mono text-sm text-text-1"
          />
        </label>
        <button
          type="button"
          onClick={() =>
            test.mutate({
              telegram_bot_token: token || undefined,
              telegram_chat_id: chatId || undefined,
            })
          }
          disabled={test.isPending}
          className="rounded-md border border-border-1 px-3 py-1.5 text-xs text-text-2 hover:text-text-1 disabled:opacity-40"
        >
          {test.isPending ? "Testing…" : "Send test message"}
        </button>
        {test.data && (
          <div
            className={
              test.data.ok ? "text-pos text-xs" : "text-neg text-xs"
            }
          >
            {test.data.ok
              ? `OK — bot @${test.data.bot_username ?? "?"}`
              : `Failed: ${test.data.error}`}
          </div>
        )}
      </fieldset>

      <fieldset className="space-y-2">
        <legend className="text-xs uppercase tracking-widest text-text-3">
          Triggers
        </legend>
        {[
          ["Signal changes (BUY⇄SELL⇄HOLD)", signalChange, setSignalChange],
          ["Every completed run", runCompleted, setRunCompleted],
          ["Failed runs", runFailed, setRunFailed],
          ["Failed schedules", scheduleFailed, setScheduleFailed],
        ].map(([label, val, setter]) => (
          <label key={label as string} className="flex items-center gap-2 text-sm text-text-2">
            <input
              type="checkbox"
              checked={val as boolean}
              onChange={(e) => (setter as (v: boolean) => void)(e.target.checked)}
            />
            {label as string}
          </label>
        ))}
        <label className="block text-xs text-text-2 mt-2">
          Confidence change threshold (0–1, blank disables)
          <input
            type="number"
            min={0}
            max={1}
            step={0.01}
            value={threshold}
            onChange={(e) => setThreshold(e.target.value)}
            className="mt-1 w-32 rounded-md border border-border-1 bg-bg-1 px-2 py-1.5 font-mono text-sm text-text-1"
          />
        </label>
      </fieldset>

      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={update.isPending}
          className="rounded-md bg-accent px-4 py-1.5 text-sm text-white hover:bg-accent/90 disabled:opacity-40"
        >
          {update.isPending ? "Saving…" : "Save"}
        </button>
        {update.isSuccess && <span className="text-pos text-xs">Saved.</span>}
      </div>
    </form>
  );
}
```

- [ ] **Step 3: 페이지**

```tsx
// web/app/(workspace)/settings/notifications/page.tsx
import { NotificationsForm } from "@/components/settings/notifications-form";

export default function SettingsNotificationsPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-lg text-text-1">Notifications</h1>
      <p className="text-sm text-text-2">
        In-app alerts are always recorded. Configure Telegram to also receive
        push notifications.
      </p>
      <NotificationsForm />
    </div>
  );
}
```

- [ ] **Step 4: Sidebar 링크 업데이트**

`web/components/nav/sidebar.tsx`의 `{ href: "/settings/llm", label: "Settings", icon: "⚙" }` 항목을 `{ href: "/settings/notifications", label: "Settings", icon: "⚙" }`로 변경. (LLM/Data settings는 M5에서 추가.)

- [ ] **Step 5: 빌드**

Run: `cd web && npx tsc --noEmit && npm run build`
Expected: 성공.

- [ ] **Step 6: 커밋**

```bash
git add web/app/\(workspace\)/settings/ web/components/settings/ web/components/nav/sidebar.tsx
git commit -m "feat(web/m4): /settings/notifications page + sidebar link"
```

---

### Task 18: 통합 테스트 (M4 happy path)

**Files:**
- Create: `tests/web/test_integration_m4.py`

- [ ] **Step 1: 테스트 작성**

```python
# tests/web/test_integration_m4.py
"""End-to-end happy path: save token → run analysis (fake) twice with
different decisions → verify signal_change alert + Telegram mock invocation.
"""
from datetime import date
from unittest.mock import AsyncMock

import pytest
from cryptography.fernet import Fernet


@pytest.fixture(autouse=True)
def _enc_key(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())


@pytest.mark.asyncio
async def test_signal_change_alert_end_to_end(
    authed_client, db_session, monkeypatch, fake_runner
):
    from tradingagents_web.api import runs as runs_api
    from tradingagents_web.services import notifier

    sender = AsyncMock(return_value=True)
    monkeypatch.setattr(notifier, "_send_telegram", sender)
    runs_api.set_background_session_factory(lambda: db_session)

    # 1. Save Telegram config
    r = authed_client.put(
        "/api/settings/notifications",
        json={"telegram_bot_token": "T:OK", "telegram_chat_id": "9"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert r.status_code == 200

    # 2. Run #1: HOLD
    fake_runner.next_decision = "HOLD"
    fake_runner.next_confidence = 0.5
    r = authed_client.post(
        "/api/runs",
        json={"ticker": "AAPL", "analysis_date": "2026-04-26"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert r.status_code == 201
    run1 = r.json()["run_id"]
    await fake_runner.wait_until_done(run1)

    # No signal_change yet (no prior)
    r = authed_client.get("/api/alerts?type=signal_change")
    assert r.json()["total"] == 0

    # 3. Run #2: BUY → triggers signal_change
    fake_runner.next_decision = "BUY"
    fake_runner.next_confidence = 0.85
    r = authed_client.post(
        "/api/runs",
        json={"ticker": "AAPL", "analysis_date": "2026-04-26"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert r.status_code == 201
    run2 = r.json()["run_id"]
    await fake_runner.wait_until_done(run2)

    # 4. Alert row exists
    r = authed_client.get("/api/alerts?type=signal_change")
    body = r.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["ticker"] == "AAPL"
    assert item["payload"]["prev"] == "HOLD"
    assert item["payload"]["curr"] == "BUY"

    # 5. Telegram mock was called
    sender.assert_awaited()

    # 6. Unread count
    r = authed_client.get("/api/alerts/unread-count")
    assert r.json()["unread"] >= 1

    # 7. Mark read clears unread
    r = authed_client.post(
        f"/api/alerts/{item['id']}/read",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert r.status_code == 200
    r = authed_client.get("/api/alerts?id=signal_change&read=true")
    # confidence_change probably also exists (delta 0.35 > 0.10)
```

(`fake_runner.next_decision` / `next_confidence`가 conftest에 없다면 추가 필요. 기존 fake_runner 인터페이스 확인 후 보강.)

- [ ] **Step 2: conftest 보강 필요 여부 확인**

Run: `grep -n "next_decision\|next_confidence\|force_error" tests/web/conftest.py`

없으면 conftest의 fake_runner 클래스에 다음 필드를 추가하고 `runner.run` 구현이 이를 반영하도록 수정:

```python
class FakeRunner:
    next_decision: str = "BUY"
    next_confidence: float = 0.7
    force_error: bool = False
    ...
    async def run(self, request):
        if self.force_error:
            raise RuntimeError("forced")
        return RunResult(
            decision=self.next_decision,
            confidence=self.next_confidence,
            ...
        )
```

기존 fake_runner 시그니처에 맞춰 보강.

- [ ] **Step 3: 테스트 실행**

Run: `pytest tests/web/test_integration_m4.py -v`
Expected: PASS.

- [ ] **Step 4: 전체 회귀 확인**

Run: `pytest tests/web -x`
Expected: 전체 PASS. M1/M2/M3 회귀 없음.

- [ ] **Step 5: 커밋**

```bash
git add tests/web/test_integration_m4.py tests/web/conftest.py
git commit -m "test(web/m4): integration test — signal change emits alert + telegram"
```

---

### Task 19: DEV.md M4 사용 절차 추가

**Files:**
- Modify: `DEV.md` (or create section if absent)

- [ ] **Step 1: M4 단락 추가**

`DEV.md`의 마일스톤 섹션 끝(M3 단락 다음)에 M4 사용 절차를 추가한다. 기존 M3 단락 형식을 그대로 따른다. 핵심 내용:

```markdown
## M4 — Alerts + Telegram

### Telegram 봇 설정 (선택)
1. BotFather로 봇 생성 → token 획득
2. 봇과 1:1 대화 시작 → `https://api.telegram.org/bot<TOKEN>/getUpdates` 로 chat_id 확인
3. 웹 UI `/settings/notifications` 에서 token, chat_id 입력 → "Send test message"

### 트리거 동작
- 시그널 변경: 같은 티커의 직전 completed 분석과 결정이 다르면 발화 (default ON)
- 신뢰도 변화: |Δ| ≥ threshold (기본 0.10) 시 (default ON, threshold UI에서 변경)
- 분석 실패 / 스케줄 실패: 항상 발화 (default ON)
- 매 완료 알림: 시끄러우니 default OFF

### 데이터
- alerts 테이블: 영구 기록, /alerts에서 필터링 + 읽음 토글
- settings 테이블: 한 행 = 한 키, telegram_bot_token만 Fernet 암호화 (ENCRYPTION_KEY 환경변수)
```

- [ ] **Step 2: 커밋**

```bash
git add DEV.md
git commit -m "docs(web/m4): document alerts + telegram setup"
```

---

## Self-Review

**Spec coverage:**
- §2 S5 (모바일에서 Telegram 알림 → PWA → 분석 상세) → tab-bar의 Alerts 항목과 `/alerts` 페이지가 모바일에서 동작 (PWA 자체는 M5).
- §3 라우트 `/alerts`, `/settings/notifications` → Tasks 15, 17.
- §6 `alerts`, `settings` 테이블 → Tasks 1–3.
- §8.1 트리거 4종 (signal_change, confidence_change, run_completed, run_failed) → Task 5(`signal_diff`) + 8(notifier).
- §8.1.4 schedule_failed → Task 9(auto_runner).
- §8.2 in-app + Telegram → Tasks 8, 10, 15, 16.
- 봇 토큰 암호화 §7 → Tasks 6 (`settings_store` Fernet).
- 응답에서 토큰 마스킹 §7 → Task 4 (`NotificationSettingsResponse`에 raw token 없음).

**Placeholder scan:** "TBD/TODO/implement later" 등 없음. 모든 step은 실행 가능한 코드 또는 명령을 포함.

**Type consistency:** 
- `signal_diff.DiffOutcome.type` 문자열 ↔ `Alert.type` 컬럼 ↔ `AlertType` enum: `signal_change | confidence_change | run_completed | run_failed | schedule_failed` 일관.
- `NotificationSettingsUpdate` 필드명 ↔ `NOTIFICATION_DEFAULTS` 키 ↔ Response 필드명: `alert_on_signal_change`/`alert_on_run_completed`/`alert_on_run_failed`/`alert_on_schedule_failed`/`confidence_change_threshold`/`telegram_bot_token`/`telegram_chat_id` 일관.
- `notifier._send_telegram` 시그니처 ↔ `telegram.send_message` 시그니처: `bot_token, chat_id, text` 키워드 인자 일관.
- `dispatch_for_analysis(analysis_id)` 인자는 PK(int), `start_analysis_run`이 `row.id`를 캡처해 전달.

**알려진 보강 지점:**
- `fake_runner` 픽스처에 `next_decision`/`next_confidence`/`force_error` 필드가 없으면 Task 9/18에서 conftest를 함께 수정해야 한다 — 각 Task의 step에 명시.
- `respx`가 dev deps에 없을 가능성 → Task 7 Step 1에서 확인 후 추가.

---

## 실행 순서 요약

1. 마이그레이션 + ORM (Tasks 1–3)
2. 스키마 + 순수 로직 (Tasks 4–5)
3. 인프라 (Tasks 6–7: settings_store + telegram client)
4. 디스패처 + 통합 (Tasks 8–9)
5. API + main.py (Tasks 10–12)
6. 프런트엔드 (Tasks 13–17)
7. E2E + 문서 (Tasks 18–19)

각 Task는 독립적으로 빌드/테스트 가능하며, 9번 직후부터 백엔드는 production-ready 상태가 된다. 프런트엔드는 17번까지 완료되면 데스크톱/모바일에서 모두 동작.
