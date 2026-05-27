"""Sector ORM — 산업/섹터 정의 (프리셋 + 사용자 정의)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tradingagents_web.models.base import Base

if TYPE_CHECKING:
    from tradingagents_web.models.sector_report import SectorReport
    from tradingagents_web.models.sector_run import SectorRun


class Sector(Base):
    __tablename__ = "sectors"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_preset: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    reports: Mapped[list["SectorReport"]] = relationship(
        back_populates="sector", cascade="all, delete-orphan"
    )
    runs: Mapped[list["SectorRun"]] = relationship(
        back_populates="sector", cascade="all, delete-orphan"
    )
