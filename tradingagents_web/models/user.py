"""Single-user account model."""
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from tradingagents_web.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """The single account for this deployment.

    Single-user app: there is only ever one row in this table.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
