"""Pydantic schemas for the hot-sector (trending) recommendation feature."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TrendingSignals(BaseModel):
    """Four normalized 0~100 signal scores behind a theme's hotness."""

    web_trend: float = Field(ge=0, le=100)
    community_volume: float = Field(ge=0, le=100)
    sentiment: float = Field(ge=0, le=100)
    momentum: float = Field(ge=0, le=100)


class TrendingSector(BaseModel):
    """A single discovered hot theme with its score and rationale."""

    name: str
    description: str = ""
    keywords: list[str] = Field(default_factory=list)
    tickers: list[str] = Field(default_factory=list)
    hotness_score: float = Field(ge=0, le=100)
    signals: TrendingSignals
    rationale: str = ""


class TrendingScanOut(BaseModel):
    """202 response body for a started trending scan."""

    job_id: str
