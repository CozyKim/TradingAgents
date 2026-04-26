"""Schedule ORM: a recurring auto-analysis cron entry."""
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from tradingagents_web.models.base import Base, utcnow


class Schedule(Base):
    """An APScheduler-backed cron entry that triggers an analysis run."""

    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    ticker: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    cron_expr: Mapped[str] = mapped_column(String(64), nullable=False)
    preset: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    last_run: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(String(16), default="user", nullable=False)
    # source: "user" | "holding" — auto-managed schedules created by holdings_sync
    holding_id: Mapped[int | None] = mapped_column(nullable=True)  # informational link

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
