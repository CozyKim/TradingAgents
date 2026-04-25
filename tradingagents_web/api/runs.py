"""Runs API: create, list, fetch, cancel, stream."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session as OrmSession
from sse_starlette.sse import EventSourceResponse

from tradingagents_web.auth import get_current_user, require_xhr
from tradingagents_web.db import SessionLocal, get_db
from tradingagents_web.models import Analysis, User
from tradingagents_web.schemas.analysis import (
    AnalysisCreateRequest,
    AnalysisCreateResponse,
    AnalysisDetail,
    AnalysisListItem,
    AnalysisListResponse,
)
from tradingagents_web.services.event_bus import AnalysisEvent, get_event_bus
from tradingagents_web.services.run_factory import make_runner
from tradingagents_web.services.runner import RunRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/runs", tags=["runs"])

# Module-level session factory — tests override this via set_background_session_factory.
_session_factory: Callable[[], OrmSession] = SessionLocal

# Strong references to background tasks so the GC doesn't collect them mid-flight.
_BACKGROUND_TASKS: set[asyncio.Task] = set()


def set_background_session_factory(factory: Callable[[], OrmSession]) -> None:
    """Override the SessionLocal used by background tasks (tests use this).

    Args:
        factory: A zero-argument callable that returns a new SQLAlchemy session.
    """
    global _session_factory
    _session_factory = factory


def _resolve_models(req: AnalysisCreateRequest) -> tuple[str, str, str]:
    """Pick LLM provider/models from request, falling back to defaults.

    Args:
        req: The incoming analysis creation request.

    Returns:
        A 3-tuple of (provider, deep_model, quick_model) strings.
    """
    from tradingagents.default_config import DEFAULT_CONFIG

    provider = req.llm_provider or DEFAULT_CONFIG["llm_provider"]
    deep = req.llm_deep_model or DEFAULT_CONFIG["deep_think_llm"]
    quick = req.llm_quick_model or DEFAULT_CONFIG["quick_think_llm"]
    return provider, deep, quick


async def _execute_and_persist(run_id: str, request: RunRequest) -> None:
    """Background task: run the analysis and write the final state to DB.

    Opens a fresh DB session independent of the request-scoped session,
    since the request session is closed before this coroutine completes.

    Args:
        run_id: The UUID string identifying this analysis run.
        request: The fully populated RunRequest describing the run.
    """
    runner = make_runner()
    db = _session_factory()
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
        except Exception as exc:  # noqa: BLE001 — record any failure
            logger.exception("Run %s failed", run_id)
            row = db.query(Analysis).filter_by(run_id=run_id).one_or_none()
            if row is not None:
                row.status = "failed"
                row.error = str(exc)[:2000]
                row.completed_at = datetime.now(timezone.utc)
                db.commit()
            bus = get_event_bus()
            if not bus.is_finished(run_id):
                bus.publish(
                    run_id,
                    AnalysisEvent(type="error", data={"message": str(exc)}),
                )
                bus.finish(run_id)
    finally:
        db.close()


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
    """Create a new analysis run row and start the background runner.

    The analysis row is persisted immediately with status="running". The
    actual runner is started as an asyncio background task so SSE clients
    can connect and replay events from the very start of the run.

    Args:
        payload: Validated request body with ticker, date, and config.
        db: Request-scoped SQLAlchemy session (injected by FastAPI).
        _user: Authenticated user (injected by FastAPI dependency).
        _csrf: XHR header CSRF guard (injected by FastAPI dependency).

    Returns:
        AnalysisCreateResponse containing the new run_id UUID string.

    Raises:
        HTTPException: 401 if not authenticated, 403 if CSRF check fails,
            422 if the request payload is invalid.
    """
    # _resolve_models reads DEFAULT_CONFIG lazily; make_runner() re-reads Settings()
    # so test monkeypatch.setenv takes effect at call time.
    provider, deep, quick = _resolve_models(payload)

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
    task = asyncio.create_task(_execute_and_persist(run_id, request))
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return AnalysisCreateResponse(run_id=run_id)


@router.get("", response_model=AnalysisListResponse)
def list_runs(
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    ticker: str | None = None,
    status_: Annotated[str | None, Query(alias="status")] = None,
    decision: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> AnalysisListResponse:
    """List analysis runs with optional filters and pagination.

    Returns runs ordered by creation time (most recent first). Supports
    filtering by ticker symbol, run status, and trading decision.

    Args:
        db: Request-scoped SQLAlchemy session (injected by FastAPI).
        _user: Authenticated user (injected by FastAPI dependency).
        ticker: Optional ticker symbol filter (case-insensitive, e.g. "AAPL").
        status_: Optional status filter ("running", "completed", "failed", "cancelled").
        decision: Optional decision filter ("BUY", "SELL", "HOLD", etc.).
        page: Page number (1-indexed, default 1).
        page_size: Items per page (1–100, default 20).

    Returns:
        AnalysisListResponse with paginated items, total count, and pagination info.

    Raises:
        HTTPException: 401 if not authenticated.
    """
    page = max(1, page)
    page_size = max(1, min(100, page_size))

    filters = []
    if ticker:
        filters.append(Analysis.ticker == ticker.strip().upper())
    if status_:
        filters.append(Analysis.status == status_)
    if decision:
        filters.append(Analysis.decision == decision.upper())

    base = select(Analysis)
    if filters:
        base = base.where(*filters)

    total_stmt = select(func.count()).select_from(Analysis)
    if filters:
        total_stmt = total_stmt.where(*filters)
    total_count = db.execute(total_stmt).scalar_one()

    rows = (
        db.execute(
            base.order_by(desc(Analysis.created_at), desc(Analysis.id))
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        .scalars()
        .all()
    )

    return AnalysisListResponse(
        items=[AnalysisListItem.model_validate(r) for r in rows],
        total=total_count,
        page=page,
        page_size=page_size,
    )


@router.get("/{run_id}", response_model=AnalysisDetail)
def get_run(
    run_id: str,
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> AnalysisDetail:
    """Return full analysis detail for a single run.

    Args:
        run_id: The unique run identifier (UUID string).
        db: Request-scoped SQLAlchemy session (injected by FastAPI).
        _user: Authenticated user (injected by FastAPI dependency).

    Returns:
        AnalysisDetail with full run state including final_state, cost, error.

    Raises:
        HTTPException: 401 if not authenticated, 404 if run_id not found.
    """
    row = db.query(Analysis).filter_by(run_id=run_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return AnalysisDetail.model_validate(row)


@router.get("/{run_id}/stream")
async def stream_run(
    run_id: str,
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
):
    """Stream analysis run events as Server-Sent Events (SSE).

    Replays buffered history immediately, then delivers live events as they
    are published. Sends a ``close`` event and terminates when the run finishes.

    Args:
        run_id: The unique run identifier to subscribe to.
        db: Request-scoped SQLAlchemy session (injected by FastAPI).
        _user: Authenticated user (injected by FastAPI dependency).

    Returns:
        EventSourceResponse streaming AnalysisEvent items as SSE.

    Raises:
        HTTPException: 401 if not authenticated, 404 if run_id not found.
    """
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
