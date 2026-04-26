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

from tradingagents_web.models import Schedule

logger = logging.getLogger(__name__)


async def trigger_run(
    schedule_id: int,
    *,
    session_factory: Callable[[], OrmSession] | None = None,
) -> str | None:
    """Fire-and-forget: load the schedule and start an analysis run.

    On any exception the session is rolled back, a schedule_failure alert
    is dispatched via the notifier, and None is returned so APScheduler
    does not rethrow.

    Args:
        schedule_id: Schedule row id.
        session_factory: Zero-arg factory returning a SQLAlchemy session.
            When None (the default), the runs API's background session
            factory is used so test overrides via
            ``runs.set_background_session_factory`` apply transparently.

    Returns:
        New run_id if started, None if the schedule was not found, inactive,
        or if an exception occurred.
    """
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
