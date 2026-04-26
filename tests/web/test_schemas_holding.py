"""Tests for Pydantic schemas under schemas/holding.py."""
import pytest

from tradingagents_web.schemas.holding import HoldingCreate, HoldingUpdate


def test_holding_create_normalizes_ticker():
    h = HoldingCreate(ticker="aapl", qty=10, avg_cost=150.0)
    assert h.ticker == "AAPL"


def test_holding_create_rejects_blank_ticker():
    with pytest.raises(ValueError):
        HoldingCreate(ticker="   ", qty=1, avg_cost=1.0)


def test_holding_create_rejects_negative_qty():
    with pytest.raises(ValueError):
        HoldingCreate(ticker="AAPL", qty=-1, avg_cost=1.0)


def test_holding_update_partial():
    u = HoldingUpdate(monitor_enabled=True)
    assert u.monitor_enabled is True
    assert u.qty is None
