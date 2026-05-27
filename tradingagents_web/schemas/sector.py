"""Pydantic schemas for /api/sectors."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator


def slugify(name: str) -> str:
    """Convert a human name to a URL-safe slug.

    Keeps ASCII letters/digits, replaces non-ASCII and whitespace with '-'.
    Collapses repeated dashes and strips edges.
    """
    s = name.lower()
    s = re.sub(r"[^\w\s-]+", "-", s, flags=re.UNICODE)
    s = re.sub(r"\s+", "-", s.strip())
    s = re.sub(r"-{2,}", "-", s)
    return s.strip("-")


ShareBasis = Literal["reported", "estimated", "unknown"]
Confidence = Literal["high", "medium", "low"]


class CompanyShare(BaseModel):
    name: str
    ticker: str | None = None
    stage: str
    share_value: float = Field(ge=0.0, le=100.0)
    share_basis: ShareBasis
    confidence: Confidence
    sources: list[HttpUrl] = Field(default_factory=list)


class CandidateTicker(BaseModel):
    ticker: str
    name: str
    stage: str
    reason: str


class SectorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    slug: str | None = None
    description: str | None = None
    keywords: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def fill_slug(self) -> SectorCreate:
        if not self.slug:
            self.slug = slugify(self.name)
        return self


class SectorOut(BaseModel):
    id: int
    slug: str
    name: str
    description: str | None
    keywords: list[str]
    is_preset: bool
    created_at: datetime
    latest_report_version: int | None = None
    latest_report_at: datetime | None = None

    model_config = {"from_attributes": True}


class SectorRunCreate(BaseModel):
    llm_quick_model: str | None = None
    llm_deep_model: str | None = None


class SectorRunOut(BaseModel):
    id: str
    sector_id: int
    status: str
    phase: str | None
    started_at: datetime
    finished_at: datetime | None
    error: str | None
    search_call_count: int

    model_config = {"from_attributes": True}


class SectorReportOut(BaseModel):
    id: int
    sector_id: int
    run_id: str
    version: int
    report_md: str
    value_chain_mermaid: str
    companies: list[CompanyShare]
    outlook_summary: str
    candidate_tickers: list[CandidateTicker]
    created_at: datetime

    model_config = {"from_attributes": True}


class SectorReportSummary(BaseModel):
    id: int
    version: int
    created_at: datetime

    model_config = {"from_attributes": True}
