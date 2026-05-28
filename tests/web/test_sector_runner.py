"""Tests for the RealSectorRunner (drives the sector LangGraph)."""

from __future__ import annotations

import asyncio
import json
from datetime import date
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage

from tradingagents_web.services.event_bus import EventBus
from tradingagents_web.services.sector_fake_runner import SectorRunRequest
from tradingagents_web.services.sector_runner import RealSectorRunner


@pytest.mark.asyncio
async def test_real_runner_progresses_through_phases():
    """RealSectorRunner emits 4 phase events, a done event, and a stitched report."""
    bus = EventBus()
    deep = MagicMock()
    deep.bind_tools.return_value = deep
    deep.invoke.side_effect = [
        AIMessage(content="# Macro"),
        AIMessage(content=json.dumps({
            "stages": [{"name": "U", "description": "", "key_companies": []}],
            "mermaid": "graph LR\n  U[U]",
        })),
        AIMessage(content=json.dumps({
            "companies": [{
                "name": "X", "stage": "U", "share_value": 10.0,
                "share_basis": "estimated", "confidence": "medium",
                "sources": [],
            }],
        })),
        AIMessage(content=json.dumps({
            "summary_md": "## OK",
            "candidate_tickers": [
                {"ticker": "X", "name": "X", "stage": "U", "reason": "..."},
            ],
        })),
    ]

    runner = RealSectorRunner(bus, llm_factory=lambda model: deep)
    request = SectorRunRequest(
        run_id="r1", sector_id=1, sector_slug="ai",
        sector_name="AI", keywords=[],
        analysis_date=date(2026, 5, 28),
    )

    events: list = []

    async def collect():
        async with bus.subscribe("r1") as queue:
            while True:
                ev = await queue.get()
                if ev is None:
                    return
                events.append(ev)

    task = asyncio.create_task(collect())
    result = await runner.run(request)
    await asyncio.wait_for(task, timeout=5.0)

    phases = [ev.data["phase"] for ev in events if ev.type == "progress"]
    assert phases == ["macro", "value_chain", "competitive", "outlook"]
    done = [ev for ev in events if ev.type == "done"]
    assert len(done) == 1
    assert done[0].data["sector_id"] == 1
    assert len(result.companies) == 1
    assert result.candidate_tickers[0]["ticker"] == "X"
    # report_md is composed from final state
    assert "AI 산업 분석" in result.report_md
    assert "X" in result.report_md
