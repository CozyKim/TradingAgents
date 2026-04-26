"""Setting ORM: key-value store for user-tunable configuration.

For sensitive values (e.g. Telegram bot token) populate ``encrypted_value`` and
leave ``value`` as None. For plain JSON-text values populate ``value``.
"""
from datetime import datetime

from sqlalchemy import DateTime, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from tradingagents_web.models.base import Base, utcnow


class Setting(Base):
    """A single configuration row addressed by a string key."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_value: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
