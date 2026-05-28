"""/api/sectors — sector CRUD + run-trigger + SSE endpoints.

CRUD endpoints mirror tradingagents_web/api/alerts.py. Run-trigger and SSE
endpoints mirror tradingagents_web/api/runs.py (module-level session
factory, asyncio background task, EventBus subscribe + sentinel loop).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as OrmSession
from sse_starlette.sse import EventSourceResponse

from tradingagents_web.auth import get_current_user, require_xhr
from tradingagents_web.db import SessionLocal, get_db
from tradingagents_web.models import Sector, SectorReport, SectorRun, User
from tradingagents_web.schemas.sector import (
    SectorCreate,
    SectorOut,
    SectorRunCreate,
    SectorRunOut,
)
from tradingagents_web.services.event_bus import (
    AnalysisEvent,
    EventBus,
    get_event_bus,
)
from tradingagents_web.services.sector_fake_runner import (
    FakeSectorRunner,
    SectorRunRequest,
)
from tradingagents_web.services.sector_runner import RealSectorRunner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sectors", tags=["sectors"])

# Module-level session factory — tests override this via
# set_background_session_factory (same pattern as runs.py).
_session_factory: Callable[[], OrmSession] = SessionLocal

# Strong references to background tasks so the GC doesn't collect them.
_BACKGROUND_TASKS: set[asyncio.Task] = set()


def set_background_session_factory(factory: Callable[[], OrmSession]) -> None:
    """Override the SessionLocal used by background tasks (tests use this).

    Args:
        factory: A zero-argument callable that returns a new SQLAlchemy session.
    """
    global _session_factory
    _session_factory = factory


def _build_runner(bus: EventBus):
    """Pick FakeSectorRunner vs RealSectorRunner based on WEB_FAKE_RUNNER.

    Args:
        bus: The shared :class:`EventBus` instance.

    Returns:
        A runner exposing an awaitable ``run(SectorRunRequest)`` method.

    Notes:
        TODO(task-later): wire a real LLM factory. Today `tradingagents_web`
        has no clean ``(model_name) -> chat`` helper, so the RealSectorRunner
        path is constructed with a placeholder factory that raises
        ``NotImplementedError`` at first use. This is fine because all current
        tests opt into ``WEB_FAKE_RUNNER=true``. Production wiring lands when
        a real LLM helper is introduced in a follow-up task.
    """
    if os.environ.get("WEB_FAKE_RUNNER", "false").lower() == "true":
        return FakeSectorRunner(bus)

    def _llm_not_wired(_model: str | None) -> object:
        raise NotImplementedError(
            "Real LLM factory for RealSectorRunner is not yet wired. "
            "Set WEB_FAKE_RUNNER=true or implement build_chat_llm in a "
            "follow-up task."
        )

    return RealSectorRunner(bus, llm_factory=_llm_not_wired)


def _to_out(sector: Sector, db: OrmSession) -> SectorOut:
    """Attach latest report metadata to a Sector row for list/detail responses."""
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
    db: Annotated[OrmSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Return all sectors (presets + user-created) with latest report meta."""
    sectors = db.execute(select(Sector).order_by(Sector.id)).scalars().all()
    return [_to_out(s, db) for s in sectors]


@router.post("", response_model=SectorOut, status_code=status.HTTP_201_CREATED)
async def create_sector(
    payload: SectorCreate,
    db: Annotated[OrmSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    _xhr: Annotated[None, Depends(require_xhr)] = None,
):
    """Create a user-defined sector. Slug is auto-derived from name when omitted."""
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
        ) from None
    db.refresh(sector)
    return _to_out(sector, db)


@router.delete("/{sector_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sector(
    sector_id: int,
    db: Annotated[OrmSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    _xhr: Annotated[None, Depends(require_xhr)] = None,
):
    """Delete a user-created sector. Presets are protected (409)."""
    sector = db.get(Sector, sector_id)
    if sector is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "sector not found")
    if sector.is_preset:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "preset sectors cannot be deleted",
        )
    db.delete(sector)
    db.commit()
    return None


# ---------------------------------------------------------------------------
# Run-trigger + SSE
# ---------------------------------------------------------------------------


@router.post(
    "/{sector_id}/runs",
    response_model=SectorRunOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_sector_run(
    sector_id: int,
    payload: SectorRunCreate,
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> SectorRunOut:
    """Start a new sector analysis run and return its SectorRunOut.

    Persists a ``sector_runs`` row with status="running" then spawns the
    background driver. Mirrors the runs.py pattern: same-sector concurrent
    runs are rejected with 409.

    Args:
        sector_id: Primary key of the target sector.
        payload: Optional LLM-model override.
        db: Request-scoped SQLAlchemy session (injected).
        _user: Authenticated user (injected).
        _csrf: XHR header CSRF guard (injected).

    Returns:
        SectorRunOut for the freshly-inserted row.

    Raises:
        HTTPException: 404 if the sector doesn't exist, 409 if another run
            for the same sector is already in ``running`` status.
    """
    sector = db.get(Sector, sector_id)
    if sector is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "sector not found")

    busy = db.execute(
        select(SectorRun)
        .where(SectorRun.sector_id == sector_id)
        .where(SectorRun.status == "running")
    ).scalar_one_or_none()
    if busy is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"sector {sector.slug} already has a running analysis ({busy.id})",
        )

    run_id = str(uuid.uuid4())
    run = SectorRun(
        id=run_id,
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

    request = SectorRunRequest(
        run_id=run_id,
        sector_id=sector_id,
        sector_slug=sector.slug,
        sector_name=sector.name,
        keywords=sector.keywords or [],
        analysis_date=datetime.now(timezone.utc).date(),
        llm_quick_model=payload.llm_quick_model,
        llm_deep_model=payload.llm_deep_model,
    )
    task = asyncio.create_task(_execute_sector_run(request))
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)

    return SectorRunOut.model_validate(run)


async def _execute_sector_run(request: SectorRunRequest) -> None:
    """Background driver — runs the (real or fake) sector runner + persists.

    Opens a fresh DB session independent of the HTTP request-scoped session
    (which is closed by FastAPI before this coroutine completes). On success
    the matching ``sector_runs`` row is flipped to ``completed`` and a new
    ``sector_reports`` row is inserted with version = max(prev) + 1.

    Args:
        request: Fully populated :class:`SectorRunRequest`.
    """
    bus = get_event_bus()
    runner = _build_runner(bus)
    db = _session_factory()
    try:
        try:
            result = await runner.run(request)
        except Exception as exc:  # noqa: BLE001 — record any failure
            logger.exception("sector_run %s failed", request.run_id)
            row = db.get(SectorRun, request.run_id)
            if row is not None:
                row.status = "failed"
                row.error = str(exc)[:2000]
                row.finished_at = datetime.now(timezone.utc)
                db.commit()
            # RealSectorRunner publishes error + finish before raising, but
            # FakeSectorRunner / unexpected paths might not — defend against
            # orphan subscribers.
            if not bus.is_finished(request.run_id):
                bus.publish(
                    request.run_id,
                    AnalysisEvent(type="error", data={"message": str(exc)}),
                )
                bus.finish(request.run_id)
            return

        row = db.get(SectorRun, request.run_id)
        if row is not None:
            row.status = "completed"
            row.phase = "outlook"
            row.finished_at = datetime.now(timezone.utc)
            row.search_call_count = result.search_call_count
            db.commit()

        # Next version = max(prev) + 1 — sector_reports has a unique constraint
        # on (sector_id, version) so we compute monotonically.
        max_version = db.execute(
            select(SectorReport.version)
            .where(SectorReport.sector_id == request.sector_id)
            .order_by(desc(SectorReport.version))
            .limit(1)
        ).scalar_one_or_none()
        next_version = (max_version or 0) + 1
        db.add(
            SectorReport(
                sector_id=request.sector_id,
                run_id=request.run_id,
                version=next_version,
                report_md=result.report_md,
                value_chain_mermaid=result.value_chain_mermaid,
                companies=result.companies,
                outlook_summary=result.outlook_summary,
                candidate_tickers=result.candidate_tickers,
                created_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
    finally:
        db.close()


@router.get("/{sector_id}/runs/{run_id}/stream")
async def stream_sector_run(
    sector_id: int,
    run_id: str,
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> EventSourceResponse:
    """SSE stream of phase events for a single sector run.

    Replays buffered history immediately, then delivers live events as they
    are published. Terminates when the producer calls :meth:`EventBus.finish`.

    Args:
        sector_id: The sector primary key (for path-consistency check).
        run_id: The run UUID to subscribe to.
        db: Request-scoped SQLAlchemy session (injected).
        _user: Authenticated user (injected).

    Returns:
        EventSourceResponse streaming :class:`AnalysisEvent` items as SSE.

    Raises:
        HTTPException: 404 if the run doesn't exist or doesn't belong to the
            given sector.
    """
    run = db.get(SectorRun, run_id)
    if run is None or run.sector_id != sector_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")

    bus = get_event_bus()

    async def event_stream():
        async with bus.subscribe(run_id) as queue:
            while True:
                ev = await queue.get()
                if ev is None:
                    yield {"event": "close", "data": "{}"}
                    return
                yield {
                    "event": ev.type,
                    "id": str(ev.seq),
                    "data": json.dumps(ev.data, ensure_ascii=False, default=str),
                }

    return EventSourceResponse(
        event_stream(),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
