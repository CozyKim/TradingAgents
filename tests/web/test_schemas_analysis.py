"""Pydantic schema tests."""
from datetime import date

import pytest
from pydantic import ValidationError

from tradingagents_web.schemas.analysis import (
    AnalysisCreateRequest,
    AnalysisListItem,
    Decision,
    Status,
)


def test_create_request_defaults():
    req = AnalysisCreateRequest(ticker="aapl", analysis_date=date(2026, 4, 25))
    assert req.ticker == "AAPL"  # uppercased
    assert req.analysts == ["market", "social", "news", "fundamentals"]
    assert req.debate_rounds == 1


def test_create_request_rejects_blank_ticker():
    with pytest.raises(ValidationError):
        AnalysisCreateRequest(ticker="", analysis_date=date(2026, 4, 25))


def test_create_request_rejects_unknown_analyst():
    with pytest.raises(ValidationError):
        AnalysisCreateRequest(
            ticker="AAPL",
            analysis_date=date(2026, 4, 25),
            analysts=["market", "bogus"],
        )


def test_decision_status_enum_values():
    assert Decision.BUY.value == "BUY"
    assert Status.RUNNING.value == "running"


def test_list_item_serializes():
    item = AnalysisListItem(
        run_id="abc",
        ticker="AAPL",
        analysis_date=date(2026, 4, 25),
        status=Status.COMPLETED,
        decision=Decision.BUY,
        confidence=0.7,
        created_at="2026-04-25T00:00:00Z",
    )
    dumped = item.model_dump()
    assert dumped["decision"] == "BUY"
