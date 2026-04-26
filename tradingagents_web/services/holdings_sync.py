"""Keep an auto-managed Schedule row in sync with Holding.monitor_enabled."""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session as OrmSession

from tradingagents_web.models import Holding, Schedule

logger = logging.getLogger(__name__)

DEFAULT_MONITOR_CRON = "30 16 * * 1-5"  # weekdays at 16:30 ET (US market close)
DEFAULT_MONITOR_TZ = "America/New_York"
DEFAULT_PRESET = {
    "analysts": ["market", "social", "news", "fundamentals"],
    "debate_rounds": 1,
}


def sync_holding_monitor(db: OrmSession, holding: Holding) -> Schedule | None:
    """Create, activate, or remove the auto schedule tied to ``holding``.

    The function must be followed by ``db.commit()`` by the caller. It does
    not commit so the caller can register/unregister the APScheduler job in
    the same DB transaction.

    Returns:
        The Schedule row if monitor is enabled, otherwise None.
    """
    existing = (
        db.query(Schedule)
        .filter_by(holding_id=holding.id, source="holding")
        .one_or_none()
    )
    if holding.monitor_enabled:
        if existing is None:
            existing = Schedule(
                name=f"Auto monitor {holding.ticker}",
                ticker=holding.ticker,
                cron_expr=DEFAULT_MONITOR_CRON,
                timezone=DEFAULT_MONITOR_TZ,
                preset=dict(DEFAULT_PRESET),
                active=True,
                source="holding",
                holding_id=holding.id,
            )
            db.add(existing)
            # Flush so a subsequent call within the same uncommitted session
            # finds this row instead of inserting a duplicate.
            db.flush()
        else:
            existing.active = True
            existing.ticker = holding.ticker
        return existing

    if existing is not None:
        db.delete(existing)
    return None
