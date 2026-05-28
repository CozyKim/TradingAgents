"""Tests for the FakeSectorRunner (WEB_FAKE_RUNNER=true mode)."""

from __future__ import annotations

import asyncio
from datetime import date

import pytest

from tradingagents_web.services.event_bus import EventBus
from tradingagents_web.services.sector_fake_runner import (
    FakeSectorRunner,
    SectorRunRequest,
)


@pytest.mark.asyncio
async def test_fake_runner_emits_four_phases():
    """FakeSectorRunner emits exactly 4 phase progress events + a done event."""
    bus = EventBus()
    runner = FakeSectorRunner(bus)
    request = SectorRunRequest(
        run_id="r1",
        sector_id=1,
        sector_slug="ai",
        sector_name="AI",
        keywords=[],
        analysis_date=date(2026, 5, 28),
    )

    events: list = []

    async def collect() -> None:
        async with bus.subscribe("r1") as queue:
            while True:
                ev = await queue.get()
                if ev is None:
                    return
                events.append(ev)

    collector = asyncio.create_task(collect())
    result = await runner.run(request)
    await asyncio.wait_for(collector, timeout=3.0)

    # 4 phase progress events then a terminal done event
    phases = [ev.data["phase"] for ev in events if ev.type == "progress"]
    assert phases == ["macro", "value_chain", "competitive", "outlook"]
    # done event carries the sector_id
    done_events = [ev for ev in events if ev.type == "done"]
    assert len(done_events) == 1
    assert done_events[0].data["sector_id"] == 1
    # Result payload has dummy report shape
    assert result.report_md.startswith("# AI 산업 분석")
    assert result.value_chain_mermaid.startswith("graph LR")
    assert len(result.candidate_tickers) >= 1
