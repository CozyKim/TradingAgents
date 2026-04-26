"""Pydantic schema tests."""
from datetime import date

import pytest
from pydantic import ValidationError

from tradingagents_web.schemas.analysis import (
    AnalysisCreateRequest,
    AnalysisListItem,
    AnalysisListResponse,
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

    dumped_json = item.model_dump(mode="json")
    assert dumped_json["decision"] == "BUY"
    assert isinstance(dumped_json["decision"], str)
    assert dumped_json["status"] == "completed"


def test_create_request_rejects_confidence_out_of_range():
    # confidence is on response models (List/Detail), not Create. Verify on AnalysisListItem.
    with pytest.raises(ValidationError):
        AnalysisListItem(
            run_id="x",
            ticker="X",
            analysis_date=date(2026, 4, 25),
            status=Status.COMPLETED,
            confidence=1.5,
            created_at="2026-04-25T00:00:00Z",
        )


def test_list_response_rejects_invalid_page():
    with pytest.raises(ValidationError):
        AnalysisListResponse(items=[], total=0, page=0, page_size=20)
