"""Tests for Pydantic schemas under schemas/schedule.py."""
import pytest

from tradingagents_web.schemas.schedule import ScheduleCreate, SchedulePreset


def test_schedule_create_validates_cron():
    s = ScheduleCreate(
        name="daily",
        ticker="aapl",
        cron_expr="30 16 * * 1-5",
        preset=SchedulePreset(analysts=["market"], debate_rounds=1),
    )
    assert s.ticker == "AAPL"


def test_schedule_create_rejects_bad_cron():
    with pytest.raises(ValueError):
        ScheduleCreate(
            name="bad",
            ticker="AAPL",
            cron_expr="not a cron",
            preset=SchedulePreset(analysts=["market"], debate_rounds=1),
        )


def test_schedule_preset_rejects_unknown_analyst():
    with pytest.raises(ValueError):
        SchedulePreset(analysts=["bogus"], debate_rounds=1)
