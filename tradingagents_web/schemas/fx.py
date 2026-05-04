"""Pydantic schemas for the FX (foreign exchange) API."""
from datetime import date, datetime

from pydantic import BaseModel


class FxRate(BaseModel):
    """USD/KRW spot rate snapshot.

    rate is None when the upstream lookup failed and no prior cache existed.
    """

    pair: str  # "USDKRW"
    rate: float | None
    as_of: date | None
    fetched_at: datetime
