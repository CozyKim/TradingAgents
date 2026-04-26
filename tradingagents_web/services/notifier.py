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
import re
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


# Telegram caps a single message at 4096 chars. Reserve headroom for the
# header + escape backslashes so the formatted message stays under the cap.
_FINAL_DECISION_MAX_CHARS = 3500

# MarkdownV2 reserved characters that must be backslash-escaped when they
# appear in dynamic text. See: https://core.telegram.org/bots/api#markdownv2-style
_MD2_SPECIAL = re.compile(r"([_*\[\]()~`>#+\-=|{}.!\\])")


def _md2(text: object) -> str:
    """Escape a value for safe interpolation into a MarkdownV2 message body."""
    return _MD2_SPECIAL.sub(r"\\\1", str(text))


def _final_decision_body(text: str | None) -> str:
    """Render the trader's final_trade_decision as escaped prose, or empty."""
    if not text:
        return ""
    body = str(text).strip()
    if not body:
        return ""
    truncated = len(body) > _FINAL_DECISION_MAX_CHARS
    if truncated:
        body = body[:_FINAL_DECISION_MAX_CHARS].rstrip()
    escaped = _md2(body)
    if truncated:
        escaped += "\n" + _md2("…(truncated)")
    return f"\n\n{escaped}"


def _format_message(outcome: DiffOutcome, *, ticker: str | None) -> str:
    """Return a MarkdownV2 message body for one DiffOutcome.

    Static markup (``*bold*``, `` `code` ``) in the headers is intentionally
    left unescaped so it renders. All dynamic values are escaped via ``_md2``.
    """
    p = outcome.payload
    tk = _md2(ticker or "?")
    if outcome.type == "signal_change":
        conf = p.get("confidence")
        conf_text = _md2(f"{conf:.2f}") if conf is not None else _md2("—")
        return (
            f"*Signal change* `{tk}`\n"
            f"{_md2(p['prev'])} → *{_md2(p['curr'])}* "
            f"\\(conf {conf_text}\\)"
            f"{_final_decision_body(p.get('final_decision_text'))}"
        )
    if outcome.type == "confidence_change":
        prev = _md2(f"{p['prev']:.2f}")
        curr = _md2(f"{p['curr']:.2f}")
        delta = _md2(f"{p['delta']:+.2f}")
        return (
            f"*Confidence shift* `{tk}`\n"
            f"{prev} → {curr} \\(Δ {delta}\\)"
        )
    if outcome.type == "run_completed":
        conf = p.get("confidence")
        conf_text = _md2(f"{conf:.2f}") if conf is not None else _md2("—")
        decision = _md2(p.get("decision") or "—")
        return (
            f"*Analysis complete* `{tk}`\n"
            f"{decision} \\(conf {conf_text}\\)"
            f"{_final_decision_body(p.get('final_decision_text'))}"
        )
    if outcome.type == "run_failed":
        err = _md2((p.get("error") or "")[:200])
        return f"*Analysis failed* `{tk}`\n{err}"
    if outcome.type == "schedule_failed":
        err = _md2((p.get("error") or "")[:200])
        return f"*Schedule failed* `{tk}`\n{err}"
    return f"Alert: {_md2(outcome.type)}"


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
