"""SectorReport ORM — 산업 분석 결과 (버전별 누적)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tradingagents_web.models.base import Base

if TYPE_CHECKING:
    from tradingagents_web.models.sector import Sector
    from tradingagents_web.models.sector_run import SectorRun


class SectorReport(Base):
    __tablename__ = "sector_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    sector_id: Mapped[int] = mapped_column(
        ForeignKey("sectors.id", ondelete="CASCADE"), index=True
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("sector_runs.id", ondelete="CASCADE"), unique=True
    )
    version: Mapped[int] = mapped_column(Integer)
    report_md: Mapped[str] = mapped_column(Text)
    value_chain_mermaid: Mapped[str] = mapped_column(Text)
    companies: Mapped[list[dict]] = mapped_column(JSON, default=list)
    outlook_summary: Mapped[str] = mapped_column(Text)
    candidate_tickers: Mapped[list[dict]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    sector: Mapped["Sector"] = relationship(back_populates="reports")
    run: Mapped["SectorRun"] = relationship(back_populates="report")

    __table_args__ = (UniqueConstraint("sector_id", "version"),)
