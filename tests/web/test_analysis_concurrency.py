"""Concurrency cap on heavy analysis graphs — fd-exhaustion regression guard.

Without a ceiling, parallel single-ticker runs (RealRunner) and sector fan-out
(RealSectorRunner) each open many file descriptors at once — LLM HTTP sockets,
yfinance/finnhub connections, cache files. Concurrent execution could exhaust
the per-process fd limit (macOS ``kern.maxfilesperproc``), surfacing downstream
as ``[Errno 24] Too many open files`` on whatever happened to request an fd at
that moment (e.g. a cache ``read_csv``).

``concurrency.analysis_slot()`` bounds how many graphs stream simultaneously so
fd usage stays ~ ``limit × per-graph peak``. These tests pin that behaviour.
"""

from __future__ import annotations

import asyncio
from datetime import date

import pytest

from tradingagents_web.services import concurrency
from tradingagents_web.services.event_bus import EventBus


@pytest.fixture(autouse=True)
def _reset_slots():
    """Drop cached per-loop semaphores so each test re-reads the env limit."""
    concurrency.reset_for_testing()
    yield
    concurrency.reset_for_testing()


async def _capacity(sem: asyncio.Semaphore) -> int:
    """Count how many times ``sem`` can be acquired before it blocks.

    Acquires until a short-timeout acquire fails, then releases everything so
    the semaphore is left untouched. Avoids reaching into ``Semaphore._value``.
    """
    acquired = 0
    try:
        while True:
            await asyncio.wait_for(sem.acquire(), timeout=0.02)
            acquired += 1
    except asyncio.TimeoutError:
        pass
    for _ in range(acquired):
        sem.release()
    return acquired


@pytest.mark.asyncio
async def test_default_limit_when_env_unset(monkeypatch):
    monkeypatch.delenv("WEB_MAX_CONCURRENT_ANALYSES", raising=False)
    concurrency.reset_for_testing()
    assert await _capacity(concurrency.analysis_slot()) == concurrency.DEFAULT_MAX_CONCURRENT


@pytest.mark.asyncio
async def test_explicit_env_limit(monkeypatch):
    monkeypatch.setenv("WEB_MAX_CONCURRENT_ANALYSES", "2")
    concurrency.reset_for_testing()
    assert await _capacity(concurrency.analysis_slot()) == 2


@pytest.mark.asyncio
async def test_invalid_env_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("WEB_MAX_CONCURRENT_ANALYSES", "not-a-number")
    concurrency.reset_for_testing()
    assert await _capacity(concurrency.analysis_slot()) == concurrency.DEFAULT_MAX_CONCURRENT


@pytest.mark.asyncio
async def test_non_positive_env_clamped_to_one(monkeypatch):
    monkeypatch.setenv("WEB_MAX_CONCURRENT_ANALYSES", "0")
    concurrency.reset_for_testing()
    assert await _capacity(concurrency.analysis_slot()) == 1


@pytest.mark.asyncio
async def test_slot_is_shared_within_a_loop(monkeypatch):
    """Both runners must share one semaphore so the cap is global, not per-call."""
    monkeypatch.setenv("WEB_MAX_CONCURRENT_ANALYSES", "3")
    concurrency.reset_for_testing()
    assert concurrency.analysis_slot() is concurrency.analysis_slot()


@pytest.mark.asyncio
async def test_real_runner_holds_slot_during_graph(monkeypatch):
    """RealRunner must run the graph while holding an analysis slot."""
    from tradingagents_web.services import runner as runner_mod
    from tradingagents_web.services.runner import RealRunner, RunRequest

    monkeypatch.setenv("WEB_MAX_CONCURRENT_ANALYSES", "1")
    monkeypatch.setenv("WEB_CONFIDENCE_JUDGE", "false")  # avoid a 2nd to_thread
    concurrency.reset_for_testing()

    captured: dict[str, bool] = {}

    async def fake_to_thread(fn, *args, **kwargs):
        # If the slot is held, a limit-1 semaphore reports locked() while the
        # graph executes — exactly what bounds concurrent fd usage.
        captured["locked_during_graph"] = concurrency.analysis_slot().locked()
        return {"final_trade_decision": "FINAL TRANSACTION PROPOSAL: **BUY**"}

    monkeypatch.setattr(runner_mod.asyncio, "to_thread", fake_to_thread)

    runner = RealRunner(bus=EventBus())
    request = RunRequest(
        run_id="rt", ticker="AAPL", analysis_date=date(2026, 5, 28),
        analysts=["market"], debate_rounds=1,
        llm_provider="openai", llm_deep_model="m", llm_quick_model="m",
    )
    await runner.run(request)
    assert captured.get("locked_during_graph") is True


@pytest.mark.asyncio
async def test_sector_runner_holds_slot_during_graph(monkeypatch):
    """RealSectorRunner must stream the sector graph while holding a slot."""
    from tradingagents_web.services import sector_runner as sr_mod
    from tradingagents_web.services.sector_fake_runner import SectorRunRequest
    from tradingagents_web.services.sector_runner import RealSectorRunner

    monkeypatch.setenv("WEB_MAX_CONCURRENT_ANALYSES", "1")
    concurrency.reset_for_testing()

    captured: dict[str, bool] = {}

    class _FakeGraph:
        async def astream(self, state):
            captured["locked_during_graph"] = concurrency.analysis_slot().locked()
            yield {"macro_overview": {"macro_report": "x"}}

    monkeypatch.setattr(sr_mod, "build_sector_graph", lambda **kw: _FakeGraph())

    runner = RealSectorRunner(EventBus(), llm_factory=lambda model: object())
    request = SectorRunRequest(
        run_id="sr", sector_id=1, sector_slug="ai",
        sector_name="AI", keywords=[], analysis_date=date(2026, 5, 28),
    )
    try:
        await runner.run(request)
    except Exception:
        # Minimal fake state may not satisfy report composition — irrelevant
        # here; the slot was already acquired before/around astream.
        pass
    assert captured.get("locked_during_graph") is True


@pytest.mark.asyncio
async def test_concurrent_runs_capped_at_limit(monkeypatch):
    """Two RealRunner.run() coroutines under limit=1 never overlap in-graph."""
    from tradingagents_web.services import runner as runner_mod
    from tradingagents_web.services.runner import RealRunner, RunRequest

    monkeypatch.setenv("WEB_MAX_CONCURRENT_ANALYSES", "1")
    monkeypatch.setenv("WEB_CONFIDENCE_JUDGE", "false")
    concurrency.reset_for_testing()

    state = {"current": 0, "peak": 0}

    async def fake_to_thread(fn, *args, **kwargs):
        state["current"] += 1
        state["peak"] = max(state["peak"], state["current"])
        await asyncio.sleep(0.05)  # hold the slot so an overlap would show
        state["current"] -= 1
        return {"final_trade_decision": "FINAL TRANSACTION PROPOSAL: **HOLD**"}

    monkeypatch.setattr(runner_mod.asyncio, "to_thread", fake_to_thread)

    def _req(rid: str) -> RunRequest:
        return RunRequest(
            run_id=rid, ticker="AAPL", analysis_date=date(2026, 5, 28),
            analysts=["market"], debate_rounds=1,
            llm_provider="openai", llm_deep_model="m", llm_quick_model="m",
        )

    runner = RealRunner(bus=EventBus())
    await asyncio.gather(runner.run(_req("a")), runner.run(_req("b")))
    assert state["peak"] == 1
