"""Tests for the hot-sector (trending) recommendation API."""

from tradingagents_web.schemas.trending import (
    TrendingScanOut,
    TrendingSector,
    TrendingSignals,
)


def test_trending_schemas_importable():
    sig = TrendingSignals(web_trend=10, community_volume=20, sentiment=30, momentum=40)
    sector = TrendingSector(name="온디바이스 AI", hotness_score=55.0, signals=sig)
    out = TrendingScanOut(job_id="abc")
    assert sector.signals.momentum == 40
    assert out.job_id == "abc"
