"""SectorRun ORM — 산업 분석 실행 1회."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tradingagents_web.models.base import Base

if TYPE_CHECKING:
    from tradingagents_web.models.sector import Sector
    from tradingagents_web.models.sector_report import SectorReport


class SectorRun(Base):
    __tablename__ = "sector_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    sector_id: Mapped[int] = mapped_column(
        ForeignKey("sectors.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(16))  # running|completed|failed
    phase: Mapped[str | None] = mapped_column(String(32), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_quick_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    llm_deep_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    search_call_count: Mapped[int] = mapped_column(Integer, default=0)

    sector: Mapped["Sector"] = relationship(back_populates="runs")
    report: Mapped["SectorReport | None"] = relationship(
        back_populates="run", uselist=False
    )
