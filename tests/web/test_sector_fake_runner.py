"""Tests for the FakeSectorRunner (WEB_FAKE_RUNNER=true mode)."""

from __future__ import annotations

from datetime import date

import pytest

from tradingagents_web.services.event_bus import EventBus
from tradingagents_web.services.sector_fake_runner import (
    FakeSectorRunner,
    SectorRunRequest,
)


@pytest.mark.asyncio
async def test_fake_runner_emits_four_phases():
    """FakeSectorRunner emits exactly 4 phase progress events; done is caller's job."""
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

    result = await runner.run(request)

    # 4 phase progress events recorded in bus history; no done/finish here —
    # the caller (api/sectors._execute_sector_run) emits those after DB commit
    # so SSE clients can't race against report persistence.
    history = bus.history("r1")
    phases = [ev.data["phase"] for ev in history if ev.type == "progress"]
    assert phases == ["macro", "value_chain", "competitive", "outlook"]
    assert all(ev.type != "done" for ev in history)
    assert not bus.is_finished("r1")
    # Result payload has dummy report shape
    assert result.report_md.startswith("# AI 산업 분석")
    assert result.value_chain_mermaid.startswith("graph LR")
    assert len(result.candidate_tickers) >= 1
