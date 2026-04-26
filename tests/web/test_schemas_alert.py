"""Tests for alert pydantic schemas."""
from datetime import datetime, timezone

from tradingagents_web.schemas.alert import (
    AlertItem,
    AlertListResponse,
    AlertType,
    UnreadCountResponse,
)


def test_alert_item_validates_type():
    item = AlertItem(
        id=1,
        type=AlertType.SIGNAL_CHANGE,
        ticker="AAPL",
        analysis_id=42,
        schedule_id=None,
        payload={"prev": "HOLD", "curr": "BUY"},
        read=False,
        created_at=datetime.now(timezone.utc),
    )
    assert item.type == AlertType.SIGNAL_CHANGE


def test_alert_list_response_pagination_bounds():
    resp = AlertListResponse(items=[], total=0, page=1, page_size=20)
    assert resp.total == 0


def test_unread_count_non_negative():
    assert UnreadCountResponse(unread=3).unread == 3
