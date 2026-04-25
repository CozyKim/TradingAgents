"""Runs API: create, list, fetch, cancel, stream."""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, status
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
    db = SessionLocal()
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
async def create_run(
    payload: AnalysisCreateRequest,
    db: Annotated[Session, Depends(get_db)],
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
    asyncio.create_task(_execute_and_persist(run_id, request))
    return AnalysisCreateResponse(run_id=run_id)
