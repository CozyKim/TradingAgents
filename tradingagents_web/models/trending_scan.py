"""TrendingScan ORM — 핫 섹터 추천 스캔 결과 (버전별 누적)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from tradingagents_web.models.base import Base


class TrendingScan(Base):
    """One completed hot-sector scan. `sectors` holds the ranked TrendingSector list."""

    __tablename__ = "trending_scans"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    sectors: Mapped[list[dict]] = mapped_column(JSON, default=list)
