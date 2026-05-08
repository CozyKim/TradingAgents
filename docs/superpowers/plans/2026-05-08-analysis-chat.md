# 분석 후속 대화 (Analysis Chat) — 구현 계획 (PR-2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 분석이 `completed`로 끝난 뒤 history/[id] 하단에서 LangChain 1.x `create_agent` 기반 어시스턴트와 후속 대화하는 기능을 구현한다. SSE 토큰 스트리밍, 분석 그래프 도구 9종 재사용, `SummarizationMiddleware`로 컨텍스트 압축, 분석별 영구 저장, 부분/취소 메시지 보관·재시도 지원.

**Architecture:**
- DB: 새 테이블 `chat_messages` 1개. 분석 row는 변경 없음.
- 백엔드: `tradingagents_web/api/chat.py`(라우트) + `services/chat_runner.py`(astream 코어) + `services/chat_context.py`(prompt+history) + `services/chat_tools.py`(도구 묶음). 기존 `services/event_bus.py`를 채널 키만 바꿔 재사용.
- 프론트: `web/components/chat/`에 4컴포넌트, `web/hooks/`에 3훅, `web/lib/`에 2모듈. `(workspace)/history/[id]/page.tsx`에 ChatSection 한 줄 삽입.
- 권한: 단일 사용자 self-host 전제 — 기존 `get_current_user` + `require_xhr`만 사용.

**Tech Stack:** FastAPI, SQLAlchemy, alembic, sse-starlette, LangChain 1.x (`create_agent`, `SummarizationMiddleware`), pytest, Next.js, React Query, EventSource, Playwright.

**Spec:** `docs/superpowers/specs/2026-05-08-analysis-chat-design.md`
**Prerequisite:** PR-1 (`docs/superpowers/plans/2026-05-08-langchain-1x-upgrade.md`) 머지됨.

---

## Phase A — 백엔드 데이터 계층

### Task 1: alembic 마이그레이션 — `chat_messages` 테이블

**Files:**
- Create: `migrations/versions/<auto>_add_chat_messages.py` (alembic이 생성)

- [ ] **Step 1: 빈 revision 생성**

Run: `uv run alembic revision -m "add chat_messages table"`
Expected: `migrations/versions/<hash>_add_chat_messages.py` 생성. 파일 경로를 기록.

- [ ] **Step 2: revision 본문 작성**

생성된 파일의 `upgrade()`/`downgrade()`를 다음으로 교체:

```python
"""add chat_messages table"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, auto-filled by alembic
revision = "<hash>"
down_revision = "<직전 head>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("analysis_id", sa.Integer(), sa.ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("turn_id", sa.String(36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content_blocks", sa.JSON(), nullable=False),
        sa.Column("tool_calls", sa.JSON(), nullable=True),
        sa.Column("tool_call_id", sa.String(64), nullable=True),
        sa.Column("tool_name", sa.String(64), nullable=True),
        sa.Column("partial", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("cancelled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error", sa.String(2048), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("model_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("analysis_id", "sequence", name="uq_chat_messages_analysis_sequence"),
    )
    op.create_index("ix_chat_messages_analysis_id", "chat_messages", ["analysis_id"])
    op.create_index("ix_chat_messages_turn_id", "chat_messages", ["turn_id"])


def downgrade() -> None:
    op.drop_index("ix_chat_messages_turn_id", table_name="chat_messages")
    op.drop_index("ix_chat_messages_analysis_id", table_name="chat_messages")
    op.drop_table("chat_messages")
```

`down_revision`은 alembic이 자동으로 채워둔 값을 그대로 사용. `revision` 해시도 자동 생성 그대로.

- [ ] **Step 3: 마이그레이션 적용**

Run: `uv run alembic upgrade head`
Expected: `chat_messages` 테이블 생성 로그.

- [ ] **Step 4: 테이블 존재 확인**

Run:
```bash
uv run python -c "
from sqlalchemy import inspect
from tradingagents_web.db import engine
print('chat_messages' in inspect(engine).get_table_names())
"
```
Expected: `True`

- [ ] **Step 5: down/up 라운드트립 검증**

Run:
```bash
uv run alembic downgrade -1
uv run alembic upgrade head
```
Expected: 두 명령 모두 에러 없이 통과.

- [ ] **Step 6: 커밋**

```bash
git add migrations/versions/<file>.py
git commit -m "feat(db): chat_messages 테이블 마이그레이션 추가"
```

---

### Task 2: ORM — `ChatMessage` 모델

**Files:**
- Create: `tradingagents_web/models/chat_message.py`
- Modify: `tradingagents_web/models/__init__.py`
- Test: `tests/test_chat_models.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_chat_models.py`:

```python
"""ChatMessage ORM 회귀 테스트."""
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from tradingagents_web.models import Analysis, ChatMessage


def _make_analysis(db) -> Analysis:
    a = Analysis(
        run_id="r-1",
        ticker="AAPL",
        analysis_date=date(2026, 5, 8),
        status="completed",
        llm_provider="openai",
        llm_deep_model="gpt-5",
        llm_quick_model="gpt-5-mini",
        debate_rounds=1,
        analysts=["market"],
    )
    db.add(a); db.commit(); db.refresh(a)
    return a


def test_insert_user_message_round_trip(db_session):
    a = _make_analysis(db_session)
    msg = ChatMessage(
        analysis_id=a.id,
        turn_id="t-1",
        sequence=0,
        role="user",
        content_blocks=[{"type": "text", "text": "안녕"}],
    )
    db_session.add(msg); db_session.commit()
    out = db_session.query(ChatMessage).filter_by(id=msg.id).one()
    assert out.role == "user"
    assert out.content_blocks == [{"type": "text", "text": "안녕"}]
    assert out.partial is False and out.cancelled is False


def test_unique_analysis_sequence(db_session):
    a = _make_analysis(db_session)
    db_session.add_all([
        ChatMessage(analysis_id=a.id, turn_id="t-1", sequence=0, role="user", content_blocks=[]),
        ChatMessage(analysis_id=a.id, turn_id="t-1", sequence=1, role="assistant", content_blocks=[]),
    ])
    db_session.commit()
    db_session.add(ChatMessage(analysis_id=a.id, turn_id="t-2", sequence=1, role="user", content_blocks=[]))
    with pytest.raises(IntegrityError):
        db_session.commit()
```

`db_session` fixture는 기존 conftest에 이미 있음(`tests/conftest.py` 확인). 없으면 conftest를 살펴 동일 패턴으로 추가.

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/test_chat_models.py -v`
Expected: `ImportError: cannot import name 'ChatMessage'` 또는 `AttributeError`로 FAIL.

- [ ] **Step 3: 모델 작성**

`tradingagents_web/models/chat_message.py`:

```python
"""ChatMessage ORM: 분석별 후속 대화 메시지."""
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from tradingagents_web.models.base import Base, utcnow


class ChatMessage(Base):
    """분석에 종속된 채팅 메시지 (user/assistant/tool)."""

    __tablename__ = "chat_messages"
    __table_args__ = (
        UniqueConstraint("analysis_id", "sequence", name="uq_chat_messages_analysis_sequence"),
        Index("ix_chat_messages_analysis_id", "analysis_id"),
        Index("ix_chat_messages_turn_id", "turn_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False)
    turn_id: Mapped[str] = mapped_column(String(36), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user|assistant|tool
    content_blocks: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    tool_calls: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    tool_call_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tool_name: Mapped[str | None] = mapped_column(String(64), nullable=True)

    partial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cancelled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 4: `__init__.py`에 export 추가**

`tradingagents_web/models/__init__.py`에 `ChatMessage` import + `__all__` 추가(기존 패턴 따라).

```python
from tradingagents_web.models.chat_message import ChatMessage  # noqa: F401
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `uv run pytest tests/test_chat_models.py -v`
Expected: 2개 PASS.

- [ ] **Step 6: 커밋**

```bash
git add tradingagents_web/models/chat_message.py tradingagents_web/models/__init__.py tests/test_chat_models.py
git commit -m "feat(models): ChatMessage ORM 추가"
```

---

### Task 3: Pydantic 스키마

**Files:**
- Create: `tradingagents_web/schemas/chat.py`

- [ ] **Step 1: 스키마 작성**

`tradingagents_web/schemas/chat.py`:

```python
"""Chat API request/response schemas."""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    analysis_id: int
    turn_id: str
    sequence: int
    role: Literal["user", "assistant", "tool"]
    content_blocks: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    partial: bool
    cancelled: bool
    error: str | None = None
    cost_usd: float | None = None
    model_id: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class ChatMessageListResponse(BaseModel):
    items: list[ChatMessageOut]
    total: int


class ChatTurnCreateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)


class ChatTurnCreateResponse(BaseModel):
    turn_id: str
```

- [ ] **Step 2: import smoke**

Run: `uv run python -c "from tradingagents_web.schemas.chat import ChatMessageOut, ChatTurnCreateRequest; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: 커밋**

```bash
git add tradingagents_web/schemas/chat.py
git commit -m "feat(schemas): chat API Pydantic 스키마 추가"
```

---

## Phase B — 백엔드 서비스 계층

### Task 4: 도구 묶음 (`chat_tools.py`)

**Files:**
- Create: `tradingagents_web/services/chat_tools.py`
- Test: `tests/test_chat_tools.py`

- [ ] **Step 1: 테스트 작성**

`tests/test_chat_tools.py`:

```python
"""채팅에 노출되는 도구 묶음 회귀 테스트."""
from tradingagents_web.services.chat_tools import CHAT_TOOLS, get_chat_tools


def test_chat_tools_are_nine():
    assert len(CHAT_TOOLS) == 9


def test_chat_tools_have_unique_names():
    names = [t.name for t in CHAT_TOOLS]
    assert len(set(names)) == 9


def test_get_chat_tools_returns_list():
    tools = get_chat_tools(analysis=None)  # 현재 시점에는 analysis-agnostic
    assert tools == CHAT_TOOLS
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_chat_tools.py -v`
Expected: `ImportError`로 FAIL.

- [ ] **Step 3: 구현**

`tradingagents_web/services/chat_tools.py`:

```python
"""채팅 어시스턴트가 호출할 수 있는 도구 묶음."""
from __future__ import annotations

from typing import Any

from tradingagents.agents.utils.agent_utils import (
    get_balance_sheet,
    get_cashflow,
    get_fundamentals,
    get_global_news,
    get_income_statement,
    get_indicators,
    get_insider_transactions,
    get_news,
    get_stock_data,
)

CHAT_TOOLS: list[Any] = [
    get_stock_data,
    get_indicators,
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
    get_news,
    get_insider_transactions,
    get_global_news,
]


def get_chat_tools(analysis: Any) -> list[Any]:
    """Return the tools available to the chat assistant.

    Currently analysis-agnostic; the analysis parameter is reserved for future
    per-analysis tool gating (e.g., disabling news for non-news analysts).
    """
    return CHAT_TOOLS
```

- [ ] **Step 4: 통과 확인 + 커밋**

Run: `uv run pytest tests/test_chat_tools.py -v`
Expected: 3개 PASS.

```bash
git add tradingagents_web/services/chat_tools.py tests/test_chat_tools.py
git commit -m "feat(chat): 분석 그래프 도구 9종을 채팅용으로 export"
```

---

### Task 5: 시스템 프롬프트 빌더

**Files:**
- Create: `tradingagents_web/services/chat_context.py` (단계적으로 작성)
- Test: `tests/test_chat_context.py` (단계적으로 추가)

- [ ] **Step 1: 시스템 프롬프트 테스트 작성**

`tests/test_chat_context.py`:

```python
"""chat_context 빌더 회귀 테스트."""
from datetime import date

from tradingagents_web.models import Analysis
from tradingagents_web.services.chat_context import build_system_prompt


def _analysis(final_state: dict | None = None, decision="BUY", confidence=0.7) -> Analysis:
    return Analysis(
        run_id="r-x",
        ticker="AAPL",
        analysis_date=date(2026, 5, 8),
        status="completed",
        decision=decision,
        confidence=confidence,
        llm_provider="openai",
        llm_deep_model="gpt-5",
        llm_quick_model="gpt-5-mini",
        debate_rounds=1,
        analysts=["market"],
        final_state=final_state or {},
    )


def test_system_prompt_includes_meta():
    prompt = build_system_prompt(_analysis())
    assert "AAPL" in prompt
    assert "2026-05-08" in prompt
    assert "BUY" in prompt
    assert "gpt-5" in prompt


def test_system_prompt_omits_empty_sections():
    prompt = build_system_prompt(_analysis(final_state={}))
    assert "📈 시장 분석" not in prompt


def test_system_prompt_includes_filled_sections():
    fs = {"market_report": "AAPL은 상승 추세", "fundamentals_report": "PE 28"}
    prompt = build_system_prompt(_analysis(final_state=fs))
    assert "📈 시장 분석" in prompt
    assert "AAPL은 상승 추세" in prompt
    assert "📊 펀더멘털" in prompt
    assert "PE 28" in prompt
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_chat_context.py -v`
Expected: `ImportError`로 FAIL.

- [ ] **Step 3: 빌더 구현**

`tradingagents_web/services/chat_context.py` (Task 6에서 추가될 것을 염두):

```python
"""시스템 프롬프트 + 메시지 히스토리 빌더 + 요약 프롬프트."""
from __future__ import annotations

from typing import Any

from tradingagents_web.models import Analysis

_REPORT_SECTIONS: list[tuple[str, str]] = [
    ("market_report", "📈 시장 분석"),
    ("sentiment_report", "💬 시장 심리"),
    ("news_report", "📰 뉴스"),
    ("fundamentals_report", "📊 펀더멘털"),
    ("investment_plan", "🧠 리서처 결론"),
    ("trader_investment_plan", "💼 트레이더 플랜"),
    ("final_trade_decision", "🎯 최종 결정"),
]


def build_system_prompt(analysis: Analysis) -> str:
    """완료된 분석 결과를 채팅 시스템 프롬프트로 변환."""
    state: dict[str, Any] = analysis.final_state or {}
    body_parts: list[str] = []
    for key, label in _REPORT_SECTIONS:
        text = state.get(key)
        if isinstance(text, str) and text.strip():
            body_parts.append(f"## {label}\n{text.strip()}")
    body = "\n\n".join(body_parts) if body_parts else "(분석 본문 없음)"

    return (
        "당신은 TradingAgents가 수행한 분석 결과를 바탕으로 후속 질문에 답하는 한국어 어시스턴트입니다.\n\n"
        "## 분석 메타\n"
        f"- 종목: {analysis.ticker}\n"
        f"- 분석일: {analysis.analysis_date}\n"
        f"- 결정: {analysis.decision} (신뢰도 {analysis.confidence})\n"
        f"- 사용 모델: {analysis.llm_provider} / deep={analysis.llm_deep_model}\n\n"
        "## 도구 사용 규칙\n"
        "- 분석 당시 데이터로 답할 수 있으면 도구를 호출하지 말고 본문 컨텍스트로 답하세요.\n"
        '- 사용자가 "지금", "최신", "오늘" 같은 표현으로 새 데이터를 요구하면 도구를 호출하세요.\n'
        f'- 도구 호출 시 ticker 기본은 "{analysis.ticker}", 분석 기준일은 "{analysis.analysis_date}"입니다.\n'
        "- 한 번의 응답에서 동일 도구를 같은 인자로 두 번 호출하지 마세요.\n\n"
        "## 응답 스타일\n"
        "- 한국어로 답하세요. 사용자가 영어로 물어도 한국어 우선.\n"
        "- 결정에 대한 근거를 묻는 질문에는 위 컨텍스트의 해당 섹션을 인용해 설명하세요.\n"
        '- 추측이 필요한 경우 "분석 시점 데이터 기준" 같은 단서를 명시하세요.\n\n'
        "## 분석 본문 (참고용 컨텍스트)\n"
        f"{body}\n"
    )
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/test_chat_context.py -v`
Expected: 3개 PASS.

- [ ] **Step 5: 커밋**

```bash
git add tradingagents_web/services/chat_context.py tests/test_chat_context.py
git commit -m "feat(chat): system_prompt 빌더 추가"
```

---

### Task 6: 메시지 히스토리 빌더 (슬라이딩 윈도우)

**Files:**
- Modify: `tradingagents_web/services/chat_context.py`
- Modify: `tests/test_chat_context.py`

- [ ] **Step 1: 테스트 추가**

`tests/test_chat_context.py`에 다음을 append:

```python
import uuid
from langchain.messages import AIMessage, HumanMessage, ToolMessage

from tradingagents_web.models import ChatMessage
from tradingagents_web.services.chat_context import build_message_history


def _add_turn(db, analysis_id, seq_start, user_text, ai_text, *, partial=False):
    tid = str(uuid.uuid4())
    db.add(ChatMessage(
        analysis_id=analysis_id, turn_id=tid, sequence=seq_start,
        role="user", content_blocks=[{"type": "text", "text": user_text}],
    ))
    db.add(ChatMessage(
        analysis_id=analysis_id, turn_id=tid, sequence=seq_start + 1,
        role="assistant", content_blocks=[{"type": "text", "text": ai_text}],
        partial=partial,
    ))
    db.commit()
    return tid


def test_history_returns_langchain_messages(db_session):
    a = _make_completed_analysis(db_session)  # helper from earlier file scope
    _add_turn(db_session, a.id, 0, "안녕", "안녕하세요")
    msgs = build_message_history(db_session, a.id, window_n=8)
    assert isinstance(msgs[0], HumanMessage)
    assert isinstance(msgs[1], AIMessage)
    assert msgs[0].content == [{"type": "text", "text": "안녕"}]


def test_history_sliding_window_keeps_last_n_turns(db_session):
    a = _make_completed_analysis(db_session)
    seq = 0
    for i in range(10):
        _add_turn(db_session, a.id, seq, f"q{i}", f"a{i}"); seq += 2
    msgs = build_message_history(db_session, a.id, window_n=3)
    # 3 turns × 2 messages = 6
    assert len(msgs) == 6
    # 최신 3개 turn(q7,q8,q9)만 유지
    user_texts = [m.content[0]["text"] for m in msgs if isinstance(m, HumanMessage)]
    assert user_texts == ["q7", "q8", "q9"]


def test_history_includes_partial_assistant(db_session):
    a = _make_completed_analysis(db_session)
    _add_turn(db_session, a.id, 0, "끊긴 질문", "끊긴 답", partial=True)
    msgs = build_message_history(db_session, a.id, window_n=8)
    assert len(msgs) == 2  # user + partial assistant 모두 포함
```

`_make_completed_analysis`는 이미 Task 2 테스트에 있는 `_make_analysis`를 모듈 상단으로 옮겨 공유. (상태를 `completed`로 명시.)

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_chat_context.py -v`
Expected: 새 3개 테스트 ImportError로 FAIL.

- [ ] **Step 3: 구현**

`tradingagents_web/services/chat_context.py`에 추가:

```python
from langchain.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from sqlalchemy.orm import Session as OrmSession

from tradingagents_web.models import ChatMessage


def _to_lc_message(row: ChatMessage) -> AnyMessage:
    if row.role == "user":
        return HumanMessage(content=row.content_blocks)
    if row.role == "assistant":
        return AIMessage(content=row.content_blocks, tool_calls=row.tool_calls or [])
    if row.role == "tool":
        return ToolMessage(
            content=row.content_blocks,
            tool_call_id=row.tool_call_id or "",
            name=row.tool_name or "",
        )
    raise ValueError(f"unknown role: {row.role}")


def build_message_history(
    db: OrmSession,
    analysis_id: int,
    *,
    window_n: int = 8,
) -> list[AnyMessage]:
    """Return the last `window_n` turns flattened as LangChain messages, in order."""
    rows: list[ChatMessage] = (
        db.query(ChatMessage)
        .filter(ChatMessage.analysis_id == analysis_id)
        .order_by(ChatMessage.sequence.asc())
        .all()
    )
    # turn_id 순서를 첫 등장순으로 보존
    seen: list[str] = []
    for r in rows:
        if r.turn_id not in seen:
            seen.append(r.turn_id)
    keep_turns = set(seen[-window_n:])
    return [_to_lc_message(r) for r in rows if r.turn_id in keep_turns]
```

- [ ] **Step 4: 통과 확인 + 커밋**

Run: `uv run pytest tests/test_chat_context.py -v`
Expected: 6개 모두 PASS.

```bash
git add tradingagents_web/services/chat_context.py tests/test_chat_context.py
git commit -m "feat(chat): 슬라이딩 윈도우 메시지 히스토리 빌더 추가"
```

---

### Task 7: 한국어 요약 프롬프트 + `summarization_middleware()` 헬퍼

**Files:**
- Modify: `tradingagents_web/services/chat_context.py`

- [ ] **Step 1: 추가**

`chat_context.py`에 append:

```python
KO_SUMMARY_PROMPT = """\
다음은 한 종목 분석 결과에 대한 사용자와 어시스턴트의 후속 대화입니다.
이전 대화의 핵심 정보를 한국어로 요약하세요.

요약 시 반드시 포함할 것:
- 사용자가 반복적으로 묻거나 강조한 관점/관심사
- 어시스턴트가 이미 호출한 도구와 그 결과의 핵심 수치(가격, 변화율, 핵심 뉴스 헤드라인 등)
- 합의된 결론이나 사용자가 수용/거부한 의견

요약은 사실 위주의 불릿 5~8개로 작성하고, 추측이나 해석을 추가하지 마세요.

[대화 내역]
{messages}
"""
```

- [ ] **Step 2: 헬퍼 import smoke**

Run: `uv run python -c "from tradingagents_web.services.chat_context import KO_SUMMARY_PROMPT; assert '{messages}' in KO_SUMMARY_PROMPT; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: 커밋**

```bash
git add tradingagents_web/services/chat_context.py
git commit -m "feat(chat): 한국어 요약 프롬프트 상수 추가"
```

---

### Task 8: 이벤트 타입 확장 + 채팅 채널 키 헬퍼

**Files:**
- Modify: `tradingagents_web/services/event_bus.py:18`
- Create: `tradingagents_web/services/chat_runner.py` (단계적으로 채워감)
- Test: `tests/test_chat_runner.py`

**전제**: 기존 `EventBus.publish`는 `run_id`(채널 키)별로 history를 자동 생성하므로 별도 `prime` 메서드 추가는 불필요. POST 직후 SSE 접속해도 publish된 이벤트는 history에서 replay된다. 단, `AnalysisEvent.type`이 Literal로 좁혀져 있어 새 채팅 타입을 허용하도록 확장이 필요.

- [ ] **Step 1: `EventType` Literal 확장**

`tradingagents_web/services/event_bus.py:18`을 다음으로 교체:

```python
EventType = Literal[
    "agent_message",
    "progress",
    "done",
    "error",
    "cancelled",
    # 채팅 turn 전용
    "token",
    "tool_call",
    "tool_result",
    "close",
]
```

- [ ] **Step 2: 테스트 작성 (이벤트 타입 + 채널 키)**

`tests/test_chat_runner.py`:

```python
"""chat_runner 단위 테스트 (외부 LLM 없이 stub)."""
from tradingagents_web.services.chat_runner import (
    ChatEvent,
    chat_channel,
)


def test_chat_event_dataclass_basic():
    ev = ChatEvent(type="token", data={"text": "hi"})
    assert ev.type == "token"
    assert ev.data == {"text": "hi"}


def test_chat_channel_format():
    assert chat_channel("run-1", "turn-1") == "chat:run-1:turn-1"
```

- [ ] **Step 3: 실패 확인 + 구현**

Run: `uv run pytest tests/test_chat_runner.py -v`
Expected: ImportError FAIL.

`tradingagents_web/services/chat_runner.py`:

```python
"""LangChain 1.x create_agent 기반 채팅 turn 실행 + SSE 발행."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ChatEvent:
    """채팅 SSE 이벤트 한 단위."""

    type: str  # token|tool_call|tool_result|done|error|cancelled|close
    data: dict[str, Any]


def chat_channel(run_id: str, turn_id: str) -> str:
    return f"chat:{run_id}:{turn_id}"
```

- [ ] **Step 4: 통과 확인 + 커밋**

Run: `uv run pytest tests/test_chat_runner.py -v`
Expected: 2개 PASS.

```bash
git add tradingagents_web/services/event_bus.py tradingagents_web/services/chat_runner.py tests/test_chat_runner.py
git commit -m "feat(chat): EventType 확장 + chat_runner 스켈레톤"
```

---

### Task 9: 모델 해석 + 미들웨어 빌더

**Files:**
- Modify: `tradingagents_web/services/chat_runner.py`
- Modify: `tests/test_chat_runner.py`

- [ ] **Step 1: 테스트 추가**

`tests/test_chat_runner.py`에 append:

```python
from datetime import date
from unittest.mock import MagicMock, patch

from tradingagents_web.models import Analysis
from tradingagents_web.services.chat_runner import (
    resolve_chat_model,
    summarization_middleware,
)


def _analysis() -> Analysis:
    return Analysis(
        run_id="r", ticker="AAPL", analysis_date=date(2026, 5, 8),
        status="completed", llm_provider="openai",
        llm_deep_model="gpt-5", llm_quick_model="gpt-5-mini",
        debate_rounds=1, analysts=["market"],
    )


def test_resolve_chat_model_uses_deep_model():
    with patch("tradingagents_web.services.chat_runner.create_llm_client") as mk:
        client = MagicMock()
        client.get_llm.return_value = "fake-llm"
        mk.return_value = client
        model = resolve_chat_model(_analysis())
        mk.assert_called_once_with(provider="openai", model="gpt-5")
        assert model == "fake-llm"


def test_summarization_middleware_uses_quick_model():
    with patch("tradingagents_web.services.chat_runner.create_llm_client") as mk, \
         patch("tradingagents_web.services.chat_runner.SummarizationMiddleware") as smw:
        client = MagicMock()
        client.get_llm.return_value = "fake-quick"
        mk.return_value = client
        summarization_middleware(_analysis())
        mk.assert_called_once_with(provider="openai", model="gpt-5-mini")
        kwargs = smw.call_args.kwargs
        assert kwargs["trigger"] == ("fraction", 0.7)
        assert kwargs["keep"] == ("messages", 12)
```

- [ ] **Step 2: 실패 확인 + 구현**

Run: `uv run pytest tests/test_chat_runner.py -v`
Expected: ImportError FAIL.

`tradingagents_web/services/chat_runner.py`에 추가:

```python
from langchain.agents.middleware import SummarizationMiddleware

from tradingagents.llm_clients import create_llm_client
from tradingagents_web.models import Analysis
from tradingagents_web.services.chat_context import KO_SUMMARY_PROMPT

CHAT_TURN_WINDOW = 8
SUMMARY_TRIGGER_FRACTION = 0.7
SUMMARY_KEEP_MESSAGES = 12


def resolve_chat_model(analysis: Analysis) -> Any:
    client = create_llm_client(provider=analysis.llm_provider, model=analysis.llm_deep_model)
    return client.get_llm()


def summarization_middleware(analysis: Analysis) -> SummarizationMiddleware:
    quick = create_llm_client(provider=analysis.llm_provider, model=analysis.llm_quick_model)
    return SummarizationMiddleware(
        model=quick.get_llm(),
        trigger=("fraction", SUMMARY_TRIGGER_FRACTION),
        keep=("messages", SUMMARY_KEEP_MESSAGES),
        summary_prompt=KO_SUMMARY_PROMPT,
    )
```

- [ ] **Step 3: 통과 확인 + 커밋**

Run: `uv run pytest tests/test_chat_runner.py -v`
Expected: 4개 모두 PASS.

```bash
git add tradingagents_web/services/chat_runner.py tests/test_chat_runner.py
git commit -m "feat(chat): 모델 해석 + SummarizationMiddleware 빌더"
```

---

### Task 10: `_execute_turn` — astream 처리 + 영속화

**Files:**
- Modify: `tradingagents_web/services/chat_runner.py`
- Modify: `tests/test_chat_runner.py`

- [ ] **Step 1: 정상/도구/오류/취소 4 케이스 테스트**

`tests/test_chat_runner.py`에 append:

```python
import asyncio
from unittest.mock import AsyncMock

from langchain.messages import AIMessageChunk
from tradingagents_web.services.chat_runner import _execute_turn
from tradingagents_web.services.event_bus import get_event_bus


class _FakeAgent:
    def __init__(self, chunks):
        self._chunks = chunks

    async def astream(self, *_args, **_kwargs):
        for c in self._chunks:
            yield c


async def _drain(channel: str) -> list:
    bus = get_event_bus()
    out = []
    async with bus.subscribe(channel) as q:
        while True:
            ev = await q.get()
            if ev is None: break
            out.append(ev)
    return out


@pytest.mark.asyncio
async def test_execute_turn_simple_text(db_session, monkeypatch):
    a = _make_completed_analysis(db_session)
    # user 메시지 사전 영속(라우트가 했을 일을 시뮬레이션)
    _add_turn_user_only(db_session, a.id, 0, "안녕")
    chunks = [
        {"type": "messages", "data": (AIMessageChunk(content="안녕하세요", chunk_position="last"), {})},
    ]
    monkeypatch.setattr(
        "tradingagents_web.services.chat_runner._build_agent",
        lambda *_: _FakeAgent(chunks),
    )
    await _execute_turn(run_id=a.run_id, analysis_id=a.id, turn_id="t-1")
    saved = db_session.query(ChatMessage).filter_by(turn_id="t-1", role="assistant").one()
    assert saved.partial is False
    assert saved.cancelled is False
    assert any(b.get("text") == "안녕하세요" for b in saved.content_blocks)


@pytest.mark.asyncio
async def test_execute_turn_runtime_error_persists_partial(db_session, monkeypatch):
    a = _make_completed_analysis(db_session)
    _add_turn_user_only(db_session, a.id, 0, "안녕")

    class _Boom:
        async def astream(self, *_a, **_k):
            yield {"type": "messages", "data": (AIMessageChunk(content="중간"), {})}
            raise RuntimeError("provider down")

    monkeypatch.setattr(
        "tradingagents_web.services.chat_runner._build_agent",
        lambda *_: _Boom(),
    )
    await _execute_turn(run_id=a.run_id, analysis_id=a.id, turn_id="t-2")
    saved = db_session.query(ChatMessage).filter_by(turn_id="t-2", role="assistant").one()
    assert saved.partial is True
    assert saved.error == "provider down"
    assert any(b.get("text") == "중간" for b in saved.content_blocks)


@pytest.mark.asyncio
async def test_execute_turn_cancellation_persists_cancelled(db_session, monkeypatch):
    a = _make_completed_analysis(db_session)
    _add_turn_user_only(db_session, a.id, 0, "긴 질문")

    class _Slow:
        async def astream(self, *_a, **_k):
            yield {"type": "messages", "data": (AIMessageChunk(content="짧은"), {})}
            await asyncio.sleep(10)

    monkeypatch.setattr(
        "tradingagents_web.services.chat_runner._build_agent",
        lambda *_: _Slow(),
    )
    task = asyncio.create_task(_execute_turn(run_id=a.run_id, analysis_id=a.id, turn_id="t-3"))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    saved = db_session.query(ChatMessage).filter_by(turn_id="t-3", role="assistant").one()
    assert saved.cancelled is True
    assert saved.partial is True
    assert saved.error is None
```

`_add_turn_user_only`는 위 fixture 모듈에 추가되는 헬퍼.

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_chat_runner.py -v`
Expected: 새 3개 ImportError/AttributeError로 FAIL.

- [ ] **Step 3: 구현**

`chat_runner.py`에 추가:

```python
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Iterable

from langchain.agents import create_agent
from langchain.messages import AIMessage, AIMessageChunk, ToolMessage
from sqlalchemy.orm import Session as OrmSession

from tradingagents_web.db import SessionLocal
from tradingagents_web.models import Analysis, ChatMessage
from tradingagents_web.services.chat_context import build_message_history, build_system_prompt
from tradingagents_web.services.chat_tools import get_chat_tools
from tradingagents_web.services.event_bus import AnalysisEvent, get_event_bus

logger = logging.getLogger(__name__)

_session_factory = SessionLocal
_RUNNING_TURNS: dict[str, asyncio.Task] = {}


def _build_agent(analysis: Analysis):
    return create_agent(
        model=resolve_chat_model(analysis),
        tools=get_chat_tools(analysis),
        system_prompt=build_system_prompt(analysis),
        middleware=[summarization_middleware(analysis)],
    )


def _next_sequence(db: OrmSession, analysis_id: int) -> int:
    last = (
        db.query(ChatMessage.sequence)
        .filter_by(analysis_id=analysis_id)
        .order_by(ChatMessage.sequence.desc())
        .first()
    )
    return (last[0] + 1) if last else 0


def _persist_assistant(
    db: OrmSession,
    *,
    analysis_id: int,
    turn_id: str,
    content_blocks: list[dict],
    tool_calls: list[dict] | None,
    model_id: str | None,
    cost_usd: float | None,
    partial: bool,
    cancelled: bool,
    error: str | None,
) -> ChatMessage:
    seq = _next_sequence(db, analysis_id)
    row = ChatMessage(
        analysis_id=analysis_id,
        turn_id=turn_id,
        sequence=seq,
        role="assistant",
        content_blocks=content_blocks,
        tool_calls=tool_calls or None,
        partial=partial,
        cancelled=cancelled,
        error=error,
        model_id=model_id,
        cost_usd=cost_usd,
        completed_at=datetime.now(timezone.utc),
    )
    db.add(row); db.commit()
    return row


def _persist_tool(
    db: OrmSession,
    *,
    analysis_id: int,
    turn_id: str,
    msg: ToolMessage,
) -> None:
    seq = _next_sequence(db, analysis_id)
    blocks = msg.content if isinstance(msg.content, list) else [{"type": "text", "text": str(msg.content)}]
    db.add(ChatMessage(
        analysis_id=analysis_id,
        turn_id=turn_id,
        sequence=seq,
        role="tool",
        content_blocks=blocks,
        tool_call_id=msg.tool_call_id,
        tool_name=msg.name,
        completed_at=datetime.now(timezone.utc),
    ))
    db.commit()


async def _execute_turn(*, run_id: str, analysis_id: int, turn_id: str) -> None:
    """analysis_id 분석의 turn_id를 백그라운드로 실행하며 SSE를 발행."""
    bus = get_event_bus()
    channel = chat_channel(run_id, turn_id)
    db = _session_factory()
    text_blocks: dict[int, str] = {}
    tool_calls_emitted: dict[str, dict] = {}
    pending_tool_messages: list[ToolMessage] = []
    final_message: AIMessage | None = None

    def _final_blocks() -> list[dict]:
        if final_message is not None and isinstance(final_message.content, list):
            return final_message.content
        if text_blocks:
            return [{"type": "text", "text": text_blocks[i]} for i in sorted(text_blocks)]
        return []

    try:
        analysis = db.query(Analysis).filter_by(id=analysis_id).one()
        # user 메시지는 라우트가 이미 commit했으므로 history에 자연스럽게 포함됨
        history = build_message_history(db, analysis_id, window_n=CHAT_TURN_WINDOW)
        agent = _build_agent(analysis)

        async for chunk in agent.astream(
            {"messages": history},
            stream_mode=["messages", "updates"],
            version="v2",
        ):
            ctype = chunk.get("type")
            data = chunk.get("data")
            if ctype == "messages":
                token, _meta = data
                if isinstance(token, AIMessageChunk):
                    if token.text:
                        bi = 0  # MVP: single text block
                        text_blocks[bi] = text_blocks.get(bi, "") + token.text
                        bus.publish(channel, AnalysisEvent(type="token", data={"text": token.text, "block_index": bi}))
            elif ctype == "updates":
                for source, update in data.items():
                    last = update["messages"][-1]
                    if source == "model" and isinstance(last, AIMessage):
                        final_message = last
                        for tc in last.tool_calls or []:
                            if tc["id"] not in tool_calls_emitted:
                                tool_calls_emitted[tc["id"]] = tc
                                bus.publish(channel, AnalysisEvent(
                                    type="tool_call",
                                    data={"id": tc["id"], "name": tc["name"], "args": tc["args"]},
                                ))
                    elif source == "tools" and isinstance(last, ToolMessage):
                        pending_tool_messages.append(last)
                        ok = not (last.status == "error") if hasattr(last, "status") else True
                        bus.publish(channel, AnalysisEvent(
                            type="tool_result",
                            data={
                                "tool_call_id": last.tool_call_id,
                                "name": last.name,
                                "content_blocks": last.content if isinstance(last.content, list) else [{"type": "text", "text": str(last.content)}],
                                "ok": ok,
                            },
                        ))

        # 정상 종료 — flush
        ai_row = _persist_assistant(
            db,
            analysis_id=analysis_id,
            turn_id=turn_id,
            content_blocks=_final_blocks(),
            tool_calls=(final_message.tool_calls if final_message else None),
            model_id=analysis.llm_deep_model,
            cost_usd=None,  # provider별 추출은 향후 확장
            partial=False,
            cancelled=False,
            error=None,
        )
        for tm in pending_tool_messages:
            _persist_tool(db, analysis_id=analysis_id, turn_id=turn_id, msg=tm)
        bus.publish(channel, AnalysisEvent(
            type="done",
            data={"sequence_end": ai_row.sequence, "model": analysis.llm_deep_model, "cost_usd": None},
        ))

    except asyncio.CancelledError:
        _persist_assistant(
            db, analysis_id=analysis_id, turn_id=turn_id,
            content_blocks=_final_blocks(), tool_calls=None,
            model_id=None, cost_usd=None,
            partial=True, cancelled=True, error=None,
        )
        bus.publish(channel, AnalysisEvent(type="cancelled", data={}))
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("chat turn %s failed", turn_id)
        _persist_assistant(
            db, analysis_id=analysis_id, turn_id=turn_id,
            content_blocks=_final_blocks(), tool_calls=None,
            model_id=None, cost_usd=None,
            partial=True, cancelled=False, error=str(exc)[:2000],
        )
        bus.publish(channel, AnalysisEvent(type="error", data={"message": str(exc)}))
    finally:
        bus.publish(channel, AnalysisEvent(type="close", data={}))
        bus.finish(channel)
        _RUNNING_TURNS.pop(turn_id, None)
        db.close()
```

`AnalysisEvent`를 채팅 이벤트로 재사용 — 기존 `event_bus`가 type/seq/data만 보므로 충분.

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_chat_runner.py -v`
Expected: 7개 모두 PASS.

- [ ] **Step 5: 커밋**

```bash
git add tradingagents_web/services/chat_runner.py tests/test_chat_runner.py
git commit -m "feat(chat): _execute_turn — astream 처리 + 영속화 + 이벤트 발행"
```

---

## Phase C — 백엔드 API 계층

### Task 11: 채팅 API 라우트

**Files:**
- Create: `tradingagents_web/api/chat.py`
- Test: `tests/test_chat_api.py`

- [ ] **Step 1: 라우트 테스트 작성**

`tests/test_chat_api.py`:

```python
"""Chat API 라우트 회귀."""
import pytest
from datetime import date

from tradingagents_web.models import Analysis, ChatMessage


def _seed_completed(db) -> Analysis:
    a = Analysis(
        run_id="r-api", ticker="AAPL", analysis_date=date(2026, 5, 8),
        status="completed", decision="BUY", confidence=0.7,
        llm_provider="openai", llm_deep_model="gpt-5", llm_quick_model="gpt-5-mini",
        debate_rounds=1, analysts=["market"],
        final_state={"market_report": "ok"},
    )
    db.add(a); db.commit(); db.refresh(a)
    return a


def test_post_turn_requires_login(client_unauth, db_session):
    a = _seed_completed(db_session)
    r = client_unauth.post(f"/api/runs/{a.run_id}/chat/turns", json={"text": "안녕"})
    assert r.status_code == 401


def test_post_turn_requires_csrf(client_no_csrf, db_session):
    a = _seed_completed(db_session)
    r = client_no_csrf.post(f"/api/runs/{a.run_id}/chat/turns", json={"text": "안녕"})
    assert r.status_code == 403


def test_post_turn_409_when_not_completed(client, db_session):
    a = _seed_completed(db_session)
    a.status = "running"; db_session.commit()
    r = client.post(f"/api/runs/{a.run_id}/chat/turns", json={"text": "안녕"})
    assert r.status_code == 409


def test_post_turn_creates_user_message_and_returns_turn_id(client, db_session, monkeypatch):
    a = _seed_completed(db_session)
    monkeypatch.setattr(
        "tradingagents_web.api.chat._spawn_turn_task", lambda *a, **k: None,  # 백그라운드 비활성
    )
    r = client.post(f"/api/runs/{a.run_id}/chat/turns", json={"text": "안녕"})
    assert r.status_code == 201
    tid = r.json()["turn_id"]
    msg = db_session.query(ChatMessage).filter_by(turn_id=tid, role="user").one()
    assert msg.content_blocks[0]["text"] == "안녕"


def test_get_messages_paginates(client, db_session):
    a = _seed_completed(db_session)
    for i in range(3):
        db_session.add(ChatMessage(
            analysis_id=a.id, turn_id=f"t{i}", sequence=i, role="user",
            content_blocks=[{"type": "text", "text": f"q{i}"}],
        ))
    db_session.commit()
    r = client.get(f"/api/runs/{a.run_id}/chat/messages")
    assert r.status_code == 200
    assert r.json()["total"] == 3
    assert len(r.json()["items"]) == 3


def test_post_turn_409_when_inflight(client, db_session, monkeypatch):
    a = _seed_completed(db_session)
    monkeypatch.setattr("tradingagents_web.api.chat._spawn_turn_task", lambda *a, **k: None)
    r1 = client.post(f"/api/runs/{a.run_id}/chat/turns", json={"text": "1"})
    assert r1.status_code == 201
    # 두 번째 turn은 진행 중 카운터로 차단
    monkeypatch.setattr("tradingagents_web.api.chat._has_inflight_turn", lambda db, aid: True)
    r2 = client.post(f"/api/runs/{a.run_id}/chat/turns", json={"text": "2"})
    assert r2.status_code == 409
```

`client`/`client_unauth`/`client_no_csrf` fixture는 conftest에 있어야 한다(없으면 기존 `tests/conftest.py`를 보고 동일 패턴으로 추가).

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_chat_api.py -v`
Expected: 라우터 미등록으로 404, 또는 ImportError로 FAIL.

- [ ] **Step 3: 구현**

`tradingagents_web/api/chat.py`:

```python
"""Chat API: 분석별 후속 대화."""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as OrmSession
from sse_starlette.sse import EventSourceResponse

from tradingagents_web.auth import get_current_user, require_xhr
from tradingagents_web.db import get_db
from tradingagents_web.models import Analysis, ChatMessage, User
from tradingagents_web.schemas.chat import (
    ChatMessageListResponse,
    ChatMessageOut,
    ChatTurnCreateRequest,
    ChatTurnCreateResponse,
)
from tradingagents_web.services.chat_runner import (
    _RUNNING_TURNS,
    _execute_turn,
    chat_channel,
)
from tradingagents_web.services.event_bus import get_event_bus

router = APIRouter(prefix="/api/runs/{run_id}/chat", tags=["chat"])


def _get_completed_analysis(db: OrmSession, run_id: str) -> Analysis:
    a = db.query(Analysis).filter_by(run_id=run_id).first()
    if a is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if a.status != "completed":
        raise HTTPException(status_code=409, detail=f"Cannot chat on a run in status '{a.status}'")
    return a


def _has_inflight_turn(db: OrmSession, analysis_id: int) -> bool:
    # 백그라운드 task가 살아있는지가 1차 신호
    if any(tid for tid in _RUNNING_TURNS):
        # 진행 중 turn이 같은 분석에 속하는지 확인 (turn_id로 ChatMessage join)
        running_turns = list(_RUNNING_TURNS.keys())
        owned = db.query(ChatMessage.turn_id).filter(
            ChatMessage.analysis_id == analysis_id,
            ChatMessage.turn_id.in_(running_turns),
        ).first()
        if owned:
            return True
    return False


def _spawn_turn_task(*, run_id: str, analysis_id: int, turn_id: str) -> None:
    task = asyncio.create_task(_execute_turn(
        run_id=run_id, analysis_id=analysis_id, turn_id=turn_id,
    ))
    _RUNNING_TURNS[turn_id] = task
    task.add_done_callback(lambda _t: _RUNNING_TURNS.pop(turn_id, None))


@router.post("/turns", response_model=ChatTurnCreateResponse, status_code=status.HTTP_201_CREATED)
def create_turn(
    run_id: str,
    payload: ChatTurnCreateRequest,
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> ChatTurnCreateResponse:
    a = _get_completed_analysis(db, run_id)
    if _has_inflight_turn(db, a.id):
        raise HTTPException(status_code=409, detail="Another turn is already in progress")

    turn_id = str(uuid.uuid4())
    last = (
        db.query(ChatMessage.sequence)
        .filter_by(analysis_id=a.id)
        .order_by(ChatMessage.sequence.desc())
        .first()
    )
    seq = (last[0] + 1) if last else 0
    db.add(ChatMessage(
        analysis_id=a.id, turn_id=turn_id, sequence=seq, role="user",
        content_blocks=[{"type": "text", "text": payload.text}],
        completed_at=datetime.now(timezone.utc),
    ))
    db.commit()

    # event_bus는 publish 시 채널 history를 자동 생성하므로 별도 prime 불필요.
    _spawn_turn_task(run_id=run_id, analysis_id=a.id, turn_id=turn_id)
    return ChatTurnCreateResponse(turn_id=turn_id)


@router.get("/messages", response_model=ChatMessageListResponse)
def list_messages(
    run_id: str,
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> ChatMessageListResponse:
    a = db.query(Analysis).filter_by(run_id=run_id).first()
    if a is None:
        raise HTTPException(status_code=404, detail="Run not found")
    rows = (
        db.query(ChatMessage)
        .filter_by(analysis_id=a.id)
        .order_by(ChatMessage.sequence.asc())
        .all()
    )
    return ChatMessageListResponse(
        items=[ChatMessageOut.model_validate(r) for r in rows],
        total=len(rows),
    )


@router.get("/turns/{turn_id}/stream")
async def stream_turn(
    run_id: str,
    turn_id: str,
    _user: Annotated[User, Depends(get_current_user)],
) -> EventSourceResponse:
    bus = get_event_bus()
    channel = chat_channel(run_id, turn_id)

    async def gen():
        async with bus.subscribe(channel) as queue:
            while True:
                ev = await queue.get()
                if ev is None:
                    return
                yield {"event": ev.type, "id": str(ev.seq), "data": json.dumps(ev.data, default=str)}

    return EventSourceResponse(
        gen(),
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.delete("/turns/{turn_id}")
def cancel_turn(
    run_id: str,
    turn_id: str,
    _user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> dict[str, bool]:
    task = _RUNNING_TURNS.get(turn_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Turn not in progress")
    task.cancel()
    return {"ok": True}
```

`from tradingagents_web.services.event_bus import get_event_bus`는 사용하지 않지만(라우트에서는 stream_turn에서만 사용), 동시 turn 가드를 위해 `_RUNNING_TURNS`만 import.

- [ ] **Step 4: 라우터 등록**

`tradingagents_web/main.py`에 import + `app.include_router(chat_api.router)` 한 줄 추가:

```python
from tradingagents_web.api import chat as chat_api
# ...
app.include_router(chat_api.router)
```

- [ ] **Step 5: 통과 확인 + 커밋**

Run: `uv run pytest tests/test_chat_api.py -v`
Expected: 6개 모두 PASS.

```bash
git add tradingagents_web/api/chat.py tradingagents_web/main.py tests/test_chat_api.py
git commit -m "feat(api): /api/runs/{run_id}/chat 라우트 추가"
```

---

## Phase D — 프론트엔드 데이터 계층

### Task 12: `lib/chat.ts` — 타입 + REST 클라이언트

**Files:**
- Create: `web/lib/chat.ts`

- [ ] **Step 1: 작성**

`web/lib/chat.ts`:

```ts
import { api } from "./api";

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export type ChatRole = "user" | "assistant" | "tool";

export interface ChatContentBlock {
  type: "text" | "reasoning" | "tool_use" | "tool_result" | "image";
  text?: string;
  [k: string]: unknown;
}

export interface ChatMessage {
  id: number;
  analysis_id: number;
  turn_id: string;
  sequence: number;
  role: ChatRole;
  content_blocks: ChatContentBlock[];
  tool_calls: { id: string; name: string; args: Record<string, unknown> }[] | null;
  tool_call_id: string | null;
  tool_name: string | null;
  partial: boolean;
  cancelled: boolean;
  error: string | null;
  cost_usd: number | null;
  model_id: string | null;
  created_at: string;
  completed_at: string | null;
}

export async function listChatMessages(runId: string): Promise<{ items: ChatMessage[]; total: number }> {
  return api(`${BASE}/api/runs/${encodeURIComponent(runId)}/chat/messages`);
}

export async function createChatTurn(runId: string, text: string): Promise<{ turn_id: string }> {
  return api(`${BASE}/api/runs/${encodeURIComponent(runId)}/chat/turns`, {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

export async function cancelChatTurn(runId: string, turnId: string): Promise<{ ok: true }> {
  return api(
    `${BASE}/api/runs/${encodeURIComponent(runId)}/chat/turns/${encodeURIComponent(turnId)}`,
    { method: "DELETE" },
  );
}
```

- [ ] **Step 2: 타입체크 smoke**

Run: `cd web && npx tsc --noEmit`
Expected: 에러 없음.

- [ ] **Step 3: 커밋**

```bash
git add web/lib/chat.ts
git commit -m "feat(web): chat REST 클라이언트 + 타입"
```

---

### Task 13: `lib/chat-sse.ts` — SSE 구독 헬퍼

**Files:**
- Create: `web/lib/chat-sse.ts`

- [ ] **Step 1: 작성**

`web/lib/chat-sse.ts`:

```ts
export type ChatSseHandlers = {
  onEvent?: (type: string, data: unknown) => void;
  onError?: (err: Event) => void;
  onClose?: () => void;
};

const TYPES = ["token", "tool_call", "tool_result", "done", "error", "cancelled", "close"] as const;

export function openChatStream(
  runId: string,
  turnId: string,
  handlers: ChatSseHandlers,
): () => void {
  const base = process.env.NEXT_PUBLIC_API_BASE ?? "";
  const url = `${base}/api/runs/${encodeURIComponent(runId)}/chat/turns/${encodeURIComponent(turnId)}/stream`;
  const es = new EventSource(url, { withCredentials: true });
  for (const t of TYPES) {
    es.addEventListener(t, (raw) => {
      let parsed: unknown = null;
      try { parsed = JSON.parse((raw as MessageEvent).data); }
      catch { parsed = (raw as MessageEvent).data; }
      handlers.onEvent?.(t, parsed);
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

- [ ] **Step 2: 타입체크**

Run: `cd web && npx tsc --noEmit`
Expected: 에러 없음.

- [ ] **Step 3: 커밋**

```bash
git add web/lib/chat-sse.ts
git commit -m "feat(web): chat SSE 구독 헬퍼"
```

---

### Task 14: `useChatMessages` 훅

**Files:**
- Create: `web/hooks/use-chat-messages.ts`

- [ ] **Step 1: 작성**

```ts
"use client";
import { useQuery } from "@tanstack/react-query";

import { listChatMessages, type ChatMessage } from "@/lib/chat";

export function useChatMessages(runId: string) {
  return useQuery<{ items: ChatMessage[]; total: number }>({
    queryKey: ["chat-messages", runId],
    queryFn: () => listChatMessages(runId),
    enabled: !!runId,
  });
}
```

- [ ] **Step 2: 타입체크 + 커밋**

Run: `cd web && npx tsc --noEmit`

```bash
git add web/hooks/use-chat-messages.ts
git commit -m "feat(web): useChatMessages 훅"
```

---

### Task 15: `useCreateChatTurn` 훅

**Files:**
- Create: `web/hooks/use-create-chat-turn.ts`

- [ ] **Step 1: 작성**

```ts
"use client";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { cancelChatTurn, createChatTurn } from "@/lib/chat";

export function useCreateChatTurn(runId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (text: string) => createChatTurn(runId, text),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["chat-messages", runId] }),
  });
}

export function useCancelChatTurn(runId: string) {
  return useMutation({
    mutationFn: (turnId: string) => cancelChatTurn(runId, turnId),
  });
}
```

- [ ] **Step 2: 타입체크 + 커밋**

```bash
git add web/hooks/use-create-chat-turn.ts
git commit -m "feat(web): useCreateChatTurn / useCancelChatTurn 훅"
```

---

### Task 16: `useChatStream` 훅 (토큰/도구 누적)

**Files:**
- Create: `web/hooks/use-chat-stream.ts`

- [ ] **Step 1: 작성**

```ts
"use client";
import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { openChatStream } from "@/lib/chat-sse";

export interface StreamingToolCall {
  id: string;
  name: string;
  args: Record<string, unknown>;
  status: "running" | "done" | "failed";
  result?: unknown;
}

export interface ChatStreamState {
  tokensByBlock: Record<number, string>;
  toolCalls: StreamingToolCall[];
  done: boolean;
  cancelled: boolean;
  error: string | null;
  cost: number | null;
  model: string | null;
}

const EMPTY: ChatStreamState = {
  tokensByBlock: {},
  toolCalls: [],
  done: false,
  cancelled: false,
  error: null,
  cost: null,
  model: null,
};

export function useChatStream(runId: string, turnId: string | null) {
  const qc = useQueryClient();
  const [state, setState] = useState<ChatStreamState>(EMPTY);
  const closeRef = useRef<() => void>();

  useEffect(() => {
    if (!turnId) {
      setState(EMPTY);
      return;
    }
    setState(EMPTY);
    closeRef.current = openChatStream(runId, turnId, {
      onEvent: (type, data) => {
        setState((s) => {
          if (type === "token") {
            const d = data as { text: string; block_index: number };
            const next = { ...s.tokensByBlock };
            next[d.block_index] = (next[d.block_index] ?? "") + d.text;
            return { ...s, tokensByBlock: next };
          }
          if (type === "tool_call") {
            const d = data as { id: string; name: string; args: Record<string, unknown> };
            return { ...s, toolCalls: [...s.toolCalls, { ...d, status: "running" }] };
          }
          if (type === "tool_result") {
            const d = data as { tool_call_id: string; ok: boolean; content_blocks: unknown };
            return {
              ...s,
              toolCalls: s.toolCalls.map((t) =>
                t.id === d.tool_call_id
                  ? { ...t, status: d.ok ? "done" : "failed", result: d.content_blocks }
                  : t,
              ),
            };
          }
          if (type === "done") {
            const d = data as { cost_usd: number | null; model: string | null };
            return { ...s, done: true, cost: d.cost_usd, model: d.model };
          }
          if (type === "error") {
            const d = data as { message: string };
            return { ...s, done: true, error: d.message };
          }
          if (type === "cancelled") {
            return { ...s, done: true, cancelled: true };
          }
          return s;
        });
      },
      onClose: () => qc.invalidateQueries({ queryKey: ["chat-messages", runId] }),
    });
    return () => closeRef.current?.();
  }, [runId, turnId, qc]);

  return state;
}
```

- [ ] **Step 2: 타입체크 + 커밋**

```bash
git add web/hooks/use-chat-stream.ts
git commit -m "feat(web): useChatStream — 토큰/도구 호출 누적 훅"
```

---

## Phase E — 프론트엔드 UI

### Task 17: 도구 호출 토글 카드

**Files:**
- Create: `web/components/chat/chat-tool-call.tsx`

- [ ] **Step 1: 작성**

```tsx
"use client";
import type { StreamingToolCall } from "@/hooks/use-chat-stream";

const STATUS_ICON: Record<StreamingToolCall["status"], string> = {
  running: "🌀",
  done: "✓",
  failed: "❌",
};

export function ChatToolCall({ call }: { call: StreamingToolCall }) {
  return (
    <details className="rounded-md border border-border-1 bg-bg-2 px-3 py-2 text-xs text-text-2">
      <summary className="cursor-pointer select-none flex items-center gap-2">
        <span className={call.status === "failed" ? "text-signal-sell" : ""}>
          {STATUS_ICON[call.status]}
        </span>
        <span className="font-mono">{call.name}({Object.keys(call.args).join(", ")})</span>
        {call.status === "running" && <span className="text-text-3">실행 중…</span>}
      </summary>
      <pre className="mt-2 whitespace-pre-wrap text-[11px] text-text-3">
{JSON.stringify({ args: call.args, result: call.result }, null, 2)}
      </pre>
    </details>
  );
}
```

- [ ] **Step 2: 커밋**

```bash
git add web/components/chat/chat-tool-call.tsx
git commit -m "feat(web): ChatToolCall 토글 컴포넌트"
```

---

### Task 18: `ChatMessage` 카드

**Files:**
- Create: `web/components/chat/chat-message.tsx`

- [ ] **Step 1: 작성**

```tsx
"use client";
import { MarkdownText } from "@/components/analysis/markdown-text";
import { Card, CardContent } from "@/components/ui/card";
import type { ChatMessage as ChatMessageT } from "@/lib/chat";
import { ChatToolCall } from "./chat-tool-call";
import type { StreamingToolCall } from "@/hooks/use-chat-stream";

export function ChatMessageCard({
  msg,
  streamingToolCalls,
  streamingText,
  cost,
  model,
}: {
  msg: ChatMessageT;
  streamingToolCalls?: StreamingToolCall[];
  streamingText?: string;
  cost?: number | null;
  model?: string | null;
}) {
  const text =
    streamingText !== undefined
      ? streamingText
      : msg.content_blocks.find((b) => b.type === "text")?.text ?? "";

  const toolCalls: StreamingToolCall[] =
    streamingToolCalls ??
    (msg.tool_calls ?? []).map((tc) => ({
      id: tc.id, name: tc.name, args: tc.args, status: "done",
    }));

  return (
    <Card>
      <CardContent className="grid gap-2 py-3">
        <div className="text-[11px] font-semibold text-text-3">
          {msg.role === "user" ? "🧑 사용자" : "🤖 어시스턴트"}
        </div>
        {toolCalls.length > 0 && (
          <div className="grid gap-1.5">
            {toolCalls.map((tc) => <ChatToolCall key={tc.id} call={tc} />)}
          </div>
        )}
        {text && <MarkdownText className="text-[13px] text-text-2" text={text} />}
        {msg.partial && msg.error && (
          <p className="text-xs text-signal-sell">응답이 중간에 끊겼어요 · {msg.error}</p>
        )}
        {msg.cancelled && (
          <p className="text-xs text-text-3">중지됨</p>
        )}
        {(model ?? msg.model_id) && (
          <p className="text-[10px] text-text-3">
            {model ?? msg.model_id}
            {(cost ?? msg.cost_usd) != null ? ` · $${(cost ?? msg.cost_usd)!.toFixed(4)}` : ""}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: 커밋**

```bash
git add web/components/chat/chat-message.tsx
git commit -m "feat(web): ChatMessageCard"
```

---

### Task 19: `ChatInput` 입력 폼

**Files:**
- Create: `web/components/chat/chat-input.tsx`

- [ ] **Step 1: 작성**

```tsx
"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";

export function ChatInput({
  disabled,
  onSubmit,
  onCancel,
  isStreaming,
}: {
  disabled: boolean;
  onSubmit: (text: string) => void;
  onCancel?: () => void;
  isStreaming: boolean;
}) {
  const [text, setText] = useState("");

  return (
    <form
      className="sticky bottom-0 grid gap-2 bg-bg-1 pt-2"
      onSubmit={(e) => {
        e.preventDefault();
        const v = text.trim();
        if (!v || disabled || isStreaming) return;
        onSubmit(v);
        setText("");
      }}
    >
      <textarea
        className="min-h-[60px] resize-y rounded-md border border-border-1 bg-bg-2 p-2 text-sm text-text-1 outline-none focus:border-accent disabled:opacity-50"
        maxLength={8000}
        disabled={disabled}
        placeholder={
          disabled
            ? "이 분석은 완료되지 않아 후속 대화를 할 수 없어요."
            : "어떤 점이 궁금하신가요? 가격 흐름·뉴스·근거를 다시 확인할 수 있어요."
        }
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
            (e.currentTarget.form as HTMLFormElement).requestSubmit();
          }
        }}
      />
      <div className="flex items-center justify-between">
        <span className="text-[11px] text-text-3">⌘/Ctrl+Enter 로 전송</span>
        <div className="flex gap-2">
          {isStreaming && onCancel && (
            <Button type="button" variant="outline" size="sm" onClick={onCancel}>
              중지
            </Button>
          )}
          <Button type="submit" size="sm" disabled={disabled || isStreaming || !text.trim()}>
            보내기
          </Button>
        </div>
      </div>
    </form>
  );
}
```

- [ ] **Step 2: 커밋**

```bash
git add web/components/chat/chat-input.tsx
git commit -m "feat(web): ChatInput 폼"
```

---

### Task 20: `ChatSection` 조립 컴포넌트

**Files:**
- Create: `web/components/chat/chat-section.tsx`

- [ ] **Step 1: 작성**

```tsx
"use client";
import { useState } from "react";

import { ChatInput } from "./chat-input";
import { ChatMessageCard } from "./chat-message";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useChatMessages } from "@/hooks/use-chat-messages";
import { useChatStream } from "@/hooks/use-chat-stream";
import { useCancelChatTurn, useCreateChatTurn } from "@/hooks/use-create-chat-turn";

export function ChatSection({ runId }: { runId: string }) {
  const messagesQ = useChatMessages(runId);
  const create = useCreateChatTurn(runId);
  const cancel = useCancelChatTurn(runId);
  const [activeTurnId, setActiveTurnId] = useState<string | null>(null);
  const stream = useChatStream(runId, activeTurnId);

  const isStreaming = !!activeTurnId && !stream.done;

  // 진행 중 turn이 끝나면 input 활성화
  if (activeTurnId && stream.done && messagesQ.isFetched) {
    // useEffect 대신 단순 비교 — done 플래그 시점에 invalidate가 끝나면 정리
    // (use-chat-stream의 onClose가 invalidate를 호출함)
  }

  const submitNew = (text: string) => {
    create.mutate(text, {
      onSuccess: ({ turn_id }) => setActiveTurnId(turn_id),
    });
  };

  const cancelNow = () => {
    if (activeTurnId) cancel.mutate(activeTurnId);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>이 분석에 대해 묻기</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-3">
        <div className="grid gap-2 max-h-[60vh] overflow-y-auto">
          {messagesQ.data?.items.map((m) => (
            <ChatMessageCard key={m.id} msg={m} />
          ))}
          {isStreaming && (
            <ChatMessageCard
              msg={{
                id: -1,
                analysis_id: 0,
                turn_id: activeTurnId!,
                sequence: 9999,
                role: "assistant",
                content_blocks: [],
                tool_calls: null,
                tool_call_id: null,
                tool_name: null,
                partial: false,
                cancelled: false,
                error: null,
                cost_usd: null,
                model_id: null,
                created_at: new Date().toISOString(),
                completed_at: null,
              }}
              streamingToolCalls={stream.toolCalls}
              streamingText={Object.values(stream.tokensByBlock).join("")}
              cost={stream.cost}
              model={stream.model}
            />
          )}
          {stream.error && !isStreaming && (
            <p className="text-xs text-signal-sell">응답이 중간에 끊겼어요 · {stream.error}</p>
          )}
        </div>
        <ChatInput
          disabled={false}
          isStreaming={isStreaming}
          onSubmit={submitNew}
          onCancel={cancelNow}
        />
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: 커밋**

```bash
git add web/components/chat/chat-section.tsx
git commit -m "feat(web): ChatSection — 메시지 목록 + 스트림 + 입력 조립"
```

---

### Task 21: `history/[id]/page.tsx`에 통합

**Files:**
- Modify: `web/app/(workspace)/history/[id]/page.tsx`

- [ ] **Step 1: 변경**

기존 페이지 끝(`</div>` 직전)에 다음 블록 삽입:

```tsx
{/* 채팅 섹션 */}
{a.status === "completed" ? (
  <ChatSection runId={id} />
) : (
  <Card>
    <CardHeader><CardTitle>후속 대화</CardTitle></CardHeader>
    <CardContent>
      <p className="text-xs text-text-3">
        이 분석은 완료되지 않아 후속 대화를 할 수 없어요.
      </p>
    </CardContent>
  </Card>
)}
```

상단 import:

```tsx
import { ChatSection } from "@/components/chat/chat-section";
```

- [ ] **Step 2: 타입체크 + 커밋**

Run: `cd web && npx tsc --noEmit`
Expected: 에러 없음.

```bash
git add web/app/\(workspace\)/history/\[id\]/page.tsx
git commit -m "feat(web): history detail에 ChatSection 통합"
```

---

## Phase F — E2E 자동화 테스트

### Task 22: Playwright E2E

**Files:**
- Create: `tests/e2e/chat.spec.ts` (Playwright 전용 — 위치는 기존 e2e 디렉터리가 있으면 그곳, 없으면 신설)

- [ ] **Step 1: Playwright 설정 확인**

Run: `cd web && npx playwright --version`
Expected: 버전 출력. 없으면 `npx playwright install`로 브라우저 설치.

- [ ] **Step 2: 테스트 작성**

(`web/tests/e2e/chat.spec.ts` — Next.js 프로젝트 안)

```ts
import { test, expect } from "@playwright/test";

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const PASSWORD = process.env.E2E_PASSWORD ?? "test1234";

async function login(page) {
  await page.goto(`${BASE}/login`);
  await page.getByLabel(/비밀번호|password/i).fill(PASSWORD);
  await page.getByRole("button", { name: /로그인|sign in/i }).click();
  await page.waitForURL(/\/(workspace|run|history)/);
}

test("completed 분석에서 채팅 시작 → 응답 토큰 + 새로고침 후 영속", async ({ page }) => {
  await login(page);
  // 가장 최근 completed 분석 진입
  await page.goto(`${BASE}/history`);
  await page.locator("a[href*='/history/']").first().click();
  await expect(page.getByText("이 분석에 대해 묻기")).toBeVisible();
  await page.locator("textarea").fill("가격 흐름 다시 보여줘");
  await page.getByRole("button", { name: "보내기" }).click();
  await expect(page.getByText(/사용자/).first()).toBeVisible();
  await expect(page.getByText(/어시스턴트/)).toBeVisible({ timeout: 60_000 });
  // 새로고침 후 그대로 보이는지
  await page.reload();
  await expect(page.getByText("가격 흐름 다시 보여줘")).toBeVisible();
});

test("failed 분석은 채팅 비활성", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/history?status=failed`);
  const failedLink = page.locator("a[href*='/history/']").first();
  if (!(await failedLink.count())) test.skip();
  await failedLink.click();
  await expect(page.getByText("이 분석은 완료되지 않아 후속 대화를 할 수 없어요.")).toBeVisible();
});
```

- [ ] **Step 3: 로컬에서 실행**

dev 서버 켠 상태에서:
Run: `cd web && npx playwright test tests/e2e/chat.spec.ts`
Expected: 2개 통과. 실패 시 trace 보고 셀렉터 보정.

- [ ] **Step 4: 커밋**

```bash
git add web/tests/e2e/chat.spec.ts web/playwright.config.ts
git commit -m "test(e2e): chat 시나리오 Playwright 자동화 추가"
```

---

## 최종 점검

- [ ] 모든 단위 테스트 PASS: `uv run pytest -x -q`
- [ ] 프론트 타입체크: `cd web && npx tsc --noEmit`
- [ ] dev 서버 띄우고 수동 시나리오(스펙 § 11.5) 1회 통과
- [ ] Playwright E2E 1회 통과
- [ ] PR-1 머지된 main 위에 본 PR이 올라가 있음을 확인 (`git log --oneline | head -5`)
- [ ] PR 본문에 스펙 링크 + 이 plan 링크 + Done 체크리스트 포함
