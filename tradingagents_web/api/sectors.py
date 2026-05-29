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
    SectorReportOut,
    SectorReportSummary,
    SectorRunCreate,
    SectorRunOut,
)
from tradingagents_web.services.event_bus import (
    AnalysisEvent,
    EventBus,
    get_event_bus,
)
from tradingagents_web.schemas.trending import TrendingScanOut
from tradingagents_web.services.sector_fake_runner import (
    FakeSectorRunner,
    SectorRunRequest,
)
from tradingagents_web.services.sector_runner import RealSectorRunner
from tradingagents_web.services.trending_finder import (
    FakeTrendingFinder,
    TrendingSectorFinder,
    search_recent,
)

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


class SectorRunnerNotConfigured(RuntimeError):
    """Production LLM wiring is not yet available for the requested provider.

    Raised at the API edge so the user sees a 503 immediately rather than
    a 202-then-silent-failure in the background task.
    """


# Defaults for the real runner. Codex OAuth is the project's preferred
# zero-API-key path (uses an existing ChatGPT Plus/Pro session). Override
# via WEB_SECTOR_LLM_PROVIDER / WEB_SECTOR_DEEP_MODEL / WEB_SECTOR_QUICK_MODEL.
_DEFAULT_SECTOR_PROVIDER = "codex_oauth"
_DEFAULT_SECTOR_DEEP_MODEL = "gpt-5.5"
_DEFAULT_SECTOR_QUICK_MODEL = "gpt-5.4-mini"


def _build_runner(bus: EventBus):
    """Pick FakeSectorRunner vs RealSectorRunner based on WEB_FAKE_RUNNER.

    For the real path, build an ``llm_factory`` from
    :func:`tradingagents.llm_clients.factory.create_llm_client` so the
    sector graph reuses the same provider catalogue as the per-ticker
    pipeline (OpenAI / Anthropic / Google / xAI / Codex OAuth / etc).
    ``ChatCodexOAuth`` and the OpenAI-style clients return LangChain
    :class:`BaseChatModel` subclasses with ``bind_tools`` implemented,
    which is exactly what the graph nodes call.

    Args:
        bus: The shared :class:`EventBus` instance.

    Returns:
        A runner exposing an awaitable ``run(SectorRunRequest)`` method.

    Raises:
        SectorRunnerNotConfigured: when the LLM client cannot be
            instantiated (e.g. missing OAuth session, unknown provider).
            The exception is caught at the API edge and turned into 503.
    """
    if os.environ.get("WEB_FAKE_RUNNER", "false").lower() == "true":
        return FakeSectorRunner(bus)

    provider = os.environ.get(
        "WEB_SECTOR_LLM_PROVIDER", _DEFAULT_SECTOR_PROVIDER
    )
    default_deep = os.environ.get(
        "WEB_SECTOR_DEEP_MODEL", _DEFAULT_SECTOR_DEEP_MODEL
    )
    default_quick = os.environ.get(
        "WEB_SECTOR_QUICK_MODEL", _DEFAULT_SECTOR_QUICK_MODEL
    )

    def llm_factory(model: str | None) -> object:
        # Lazy import: keeps web tests fast and avoids loading langgraph LLM
        # adapters until a real run actually starts.
        from tradingagents.llm_clients.factory import create_llm_client

        chosen = model or default_deep
        try:
            return create_llm_client(provider, chosen).get_llm()
        except Exception as exc:  # noqa: BLE001 — surface a clean 503 message
            raise SectorRunnerNotConfigured(
                f"Failed to build LLM client (provider={provider}, "
                f"model={chosen}): {exc}"
            ) from exc

    # Eagerly probe the deep model so a misconfigured provider 503s at the
    # API edge instead of failing inside the background task.
    llm_factory(default_quick)

    return RealSectorRunner(bus, llm_factory=llm_factory)


def _build_trending_finder(bus: EventBus):
    """FakeTrendingFinder when WEB_FAKE_RUNNER, else a wired real finder.

    Args:
        bus: The shared :class:`EventBus` instance.

    Returns:
        A finder exposing an awaitable ``find(job_id)`` method.
    """
    if os.environ.get("WEB_FAKE_RUNNER", "false").lower() == "true":
        return FakeTrendingFinder(bus)

    provider = os.environ.get("WEB_SECTOR_LLM_PROVIDER", _DEFAULT_SECTOR_PROVIDER)
    model = os.environ.get("WEB_SECTOR_DEEP_MODEL", _DEFAULT_SECTOR_DEEP_MODEL)

    def llm_json(prompt: str) -> str:
        from tradingagents.llm_clients.base_client import normalize_content
        from tradingagents.llm_clients.factory import create_llm_client

        llm = create_llm_client(provider, model).get_llm()
        return normalize_content(llm.invoke(prompt)).content

    def social_fn(ticker: str) -> dict:
        from tradingagents.dataflows.stocktwits import get_social_messages_stocktwits

        md = get_social_messages_stocktwits(ticker, limit=50)
        bullish = md.count("(Bullish)")
        bearish = md.count("(Bearish)")
        total = md.count("\n- [")
        return {"bullish": bullish, "bearish": bearish, "total_messages": total}

    def momentum_fn(ticker: str) -> dict:
        import yfinance as yf

        hist = yf.Ticker(ticker).history(period="1mo")
        if hist.empty or len(hist) < 6:
            return {"avg_return_pct": 0.0}
        recent = hist["Close"].iloc[-1]
        prior = hist["Close"].iloc[-6]
        ret = (recent - prior) / prior * 100.0 if prior else 0.0
        return {"avg_return_pct": float(ret)}

    return TrendingSectorFinder(
        bus,
        llm_json=llm_json,
        search_fn=search_recent,
        social_fn=social_fn,
        momentum_fn=momentum_fn,
        today=datetime.now(timezone.utc).date(),
    )


@router.post(
    "/trending",
    response_model=TrendingScanOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_trending_scan(
    _user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> TrendingScanOut:
    """Start a background hot-sector scan and return its SSE job_id."""
    bus = get_event_bus()
    finder = _build_trending_finder(bus)
    job_id = str(uuid.uuid4())
    task = asyncio.create_task(_execute_trending_scan(finder, job_id))
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return TrendingScanOut(job_id=job_id)


async def _execute_trending_scan(finder, job_id: str) -> None:
    """Background driver: run finder, publish done(sectors) + finish.

    Args:
        finder: A TrendingSectorFinder or FakeTrendingFinder instance.
        job_id: EventBus run-id to publish events under.
    """
    bus = get_event_bus()
    try:
        sectors = await finder.find(job_id)
        bus.publish(
            job_id,
            AnalysisEvent(
                type="done",
                data={"sectors": [s.model_dump() for s in sectors]},
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("trending scan %s failed", job_id)
        bus.publish(job_id, AnalysisEvent(type="error", data={"message": str(exc)}))
    finally:
        bus.finish(job_id)


@router.get("/trending/{job_id}/stream")
async def stream_trending_scan(
    job_id: str,
    _user: Annotated[User, Depends(get_current_user)],
) -> EventSourceResponse:
    """SSE stream of a trending scan's progress + terminal done/error.

    Args:
        job_id: The scan UUID to subscribe to.
        _user: Authenticated user (injected).

    Returns:
        EventSourceResponse streaming :class:`AnalysisEvent` items as SSE.
    """
    bus = get_event_bus()

    async def event_stream():
        async with bus.subscribe(job_id) as queue:
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
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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

    # Fail fast at the edge if the runner can't be built — we'd rather 503
    # the request than 202-then-silent-fail in the background driver.
    try:
        _build_runner(get_event_bus())
    except SectorRunnerNotConfigured as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)
        ) from exc

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

        # Compute next version + insert the SectorReport AND flip status in
        # a single transaction — otherwise a SSE client reacting to `done`
        # could race against report persistence. The runner intentionally
        # does NOT publish `done` / `bus.finish()`; we do it below AFTER the
        # commit succeeds so observers can trust that the latest report is
        # visible by the time they see completion.
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
        row = db.get(SectorRun, request.run_id)
        if row is not None:
            row.status = "completed"
            row.phase = "outlook"
            row.finished_at = datetime.now(timezone.utc)
            row.search_call_count = result.search_call_count
        db.commit()

        # All persistence done — now safe to signal completion. Order matters:
        # `done` before `finish` so the sentinel arrives last and subscribers
        # can rely on `done.data["sector_id"]` to know which sector to refresh.
        bus.publish(
            request.run_id,
            AnalysisEvent(type="done", data={"sector_id": request.sector_id}),
        )
        bus.finish(request.run_id)
    finally:
        db.close()


@router.get("/{sector_id}/runs/active", response_model=SectorRunOut | None)
async def get_active_sector_run(
    sector_id: int,
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> SectorRunOut | None:
    """Return the currently-running SectorRun for this sector, if any.

    Polled by the detail page so a user who navigates away and returns
    still sees "분석 진행 중" with the latest phase, and can re-subscribe
    to the SSE stream by run_id.
    """
    row = db.execute(
        select(SectorRun)
        .where(SectorRun.sector_id == sector_id)
        .where(SectorRun.status == "running")
        .order_by(desc(SectorRun.started_at))
        .limit(1)
    ).scalar_one_or_none()
    return SectorRunOut.model_validate(row) if row is not None else None


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


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


@router.get(
    "/{sector_id}/reports", response_model=list[SectorReportSummary]
)
async def list_reports(
    sector_id: int,
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> list[SectorReportSummary]:
    """List report versions for a sector, newest first."""
    rows = db.execute(
        select(SectorReport)
        .where(SectorReport.sector_id == sector_id)
        .order_by(desc(SectorReport.version))
    ).scalars().all()
    return [SectorReportSummary.model_validate(r) for r in rows]


@router.get(
    "/{sector_id}/reports/latest", response_model=SectorReportOut
)
async def get_latest_report(
    sector_id: int,
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> SectorReportOut:
    """Return the highest-version report for a sector, or 404 if none."""
    row = db.execute(
        select(SectorReport)
        .where(SectorReport.sector_id == sector_id)
        .order_by(desc(SectorReport.version))
        .limit(1)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no reports yet")
    return SectorReportOut.model_validate(row)


@router.get(
    "/{sector_id}/reports/{report_id}", response_model=SectorReportOut
)
async def get_report(
    sector_id: int,
    report_id: int,
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> SectorReportOut:
    """Return a specific report. 404 if missing OR if it belongs to a different sector."""
    row = db.get(SectorReport, report_id)
    if row is None or row.sector_id != sector_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "report not found")
    return SectorReportOut.model_validate(row)
