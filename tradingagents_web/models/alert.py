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
