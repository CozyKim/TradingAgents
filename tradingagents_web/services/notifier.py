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
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session as OrmSession

from tradingagents_web.models import Alert, Analysis
from tradingagents_web.services import settings_store, telegram
from tradingagents_web.services.signal_diff import DiffOutcome, diff_for_completion

logger = logging.getLogger(__name__)


# Indirection so tests can monkeypatch a single hook.
async def _send_telegram(*, bot_token: str, chat_id: str, text: str) -> bool:
    return await telegram.send_message(
        bot_token=bot_token, chat_id=chat_id, text=text
    )


def _format_message(outcome: DiffOutcome, *, ticker: str | None) -> str:
    """Return a Markdown message body for one DiffOutcome."""
    p = outcome.payload
    if outcome.type == "signal_change":
        conf = p.get("confidence")
        conf_text = f"{conf:.2f}" if conf is not None else "—"
        return (
            f"*Signal change* `{ticker}`\n"
            f"{p['prev']} → *{p['curr']}* (conf {conf_text})"
        )
    if outcome.type == "confidence_change":
        return (
            f"*Confidence shift* `{ticker}`\n"
            f"{p['prev']:.2f} → {p['curr']:.2f} (Δ {p['delta']:+.2f})"
        )
    if outcome.type == "run_completed":
        conf = p.get("confidence")
        conf_text = f"{conf:.2f}" if conf is not None else "—"
        return (
            f"*Analysis complete* `{ticker}`\n"
            f"{p.get('decision')} (conf {conf_text})"
        )
    if outcome.type == "run_failed":
        return f"*Analysis failed* `{ticker}`\n{(p.get('error') or '')[:200]}"
    if outcome.type == "schedule_failed":
        return (
            f"*Schedule failed* `{ticker or '?'}`\n"
            f"{(p.get('error') or '')[:200]}"
        )
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
    """Emit a schedule_failed alert (in-app + telegram if enabled).

    Args:
        schedule_id: PK of the schedule that failed.
        ticker: Ticker symbol associated with the schedule, if known.
        error: Human-readable error description.
        session_factory: Zero-arg callable returning a SQLAlchemy session.
    """
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
    cfg: dict[str, Any],
) -> None:
    """Insert Alert rows for each outcome and fan out to Telegram if configured.

    Args:
        db: Active SQLAlchemy session (caller owns open/close).
        outcomes: List of DiffOutcome instances to persist.
        ticker: Ticker symbol for the Alert rows.
        analysis_id: FK to analyses table, or None for schedule-only alerts.
        schedule_id: FK to schedules table, or None for manual runs.
        cfg: Notification config from ``settings_store.load_notification_config``.
    """
    if not outcomes:
        return

    for o in outcomes:
        db.add(
            Alert(
                type=o.type,
                ticker=ticker,
                analysis_id=analysis_id,
                schedule_id=schedule_id,
                payload=o.payload,
                read=False,
                created_at=datetime.now(timezone.utc),
            )
        )
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
    results = await asyncio.gather(*sends, return_exceptions=True)
    for r in results:
        if isinstance(r, Exception):
            logger.warning("telegram fanout exception swallowed: %s", r)
