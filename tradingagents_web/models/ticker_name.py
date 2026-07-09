"""TickerName ORM: persistent ticker → display-name cache."""
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from tradingagents_web.models.base import Base, TimestampMixin


class TickerName(Base, TimestampMixin):
    """티커 하나에 대한 표시명(한글 우선) 캐시.

    해석 실패는 저장하지 않는다(``name`` NOT NULL). 신규 상장주가 "이름 없음"으로
    영구 고착되는 것을 막기 위함이며, 실패는 서비스 계층의 negative 캐시가 흡수한다.
    """

    __tablename__ = "ticker_names"

    ticker: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
