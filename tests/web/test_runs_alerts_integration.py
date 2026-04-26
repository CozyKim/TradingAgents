"""Verify _execute_and_persist invokes notifier on completion and failure."""
import asyncio
from datetime import date

import pytest

from tradingagents_web.api import runs as runs_api
from tradingagents_web.services import notifier


@pytest.mark.asyncio
async def test_completion_invokes_notifier(monkeypatch, app_with_test_db):
    """When a run completes, notifier.dispatch_for_analysis is awaited."""
    monkeypatch.setenv("WEB_FAKE_RUNNER", "true")
    monkeypatch.setenv("WEB_FAKE_RUNNER_DELAY_SECONDS", "0")

    awaited_with: list[int] = []

    async def fake_dispatch(analysis_id, *, session_factory):
        awaited_with.append(analysis_id)

    monkeypatch.setattr(notifier, "dispatch_for_analysis", fake_dispatch)

    _, TestSessionLocal = app_with_test_db

    db = TestSessionLocal()
    try:
        runs_api.start_analysis_run(
            db,
            ticker="AAPL",
            analysis_date=date(2026, 4, 26),
            analysts=["market"],
            debate_rounds=1,
            llm_provider="openai",
            llm_deep_model="gpt-4",
            llm_quick_model="gpt-4-mini",
        )
    finally:
        db.close()

    # Wait for the background _execute_and_persist task to finish (up to 10s)
    for _ in range(200):
        if awaited_with:
            break
        await asyncio.sleep(0.05)

    assert awaited_with, "notifier.dispatch_for_analysis was never awaited"
    assert isinstance(awaited_with[0], int)
