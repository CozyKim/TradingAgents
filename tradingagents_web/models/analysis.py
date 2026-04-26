"""Analysis ORM: stores every analysis run, in-progress and completed."""
from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Date, DateTime, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from tradingagents_web.models.base import Base, utcnow


class Analysis(Base):
    """A single analysis run (one ticker, one date, one config)."""

    __tablename__ = "analyses"
    __table_args__ = (
        Index("ix_analyses_ticker_created", "ticker", "created_at"),
        Index("ix_analyses_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    ticker: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    analysis_date: Mapped[date] = mapped_column(Date, nullable=False)

    status: Mapped[str] = mapped_column(String(16), nullable=False)  # running|completed|failed|cancelled
    decision: Mapped[str | None] = mapped_column(String(16), nullable=True)  # BUY|SELL|HOLD|OVERWEIGHT|UNDERWEIGHT
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    llm_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    llm_deep_model: Mapped[str] = mapped_column(String(64), nullable=False)
    llm_quick_model: Mapped[str] = mapped_column(String(64), nullable=False)
    debate_rounds: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    analysts: Mapped[list[str]] = mapped_column(JSON, nullable=False)

    final_state: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    schedule_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
