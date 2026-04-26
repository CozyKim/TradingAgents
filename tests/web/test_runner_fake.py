"""Fake runner emits a deterministic event sequence for tests/dev."""
from datetime import date

from tradingagents_web.services.event_bus import EventBus
from tradingagents_web.services.runner import FakeRunner, RunRequest, _extract_decision


async def test_fake_runner_emits_progress_then_done():
    bus = EventBus()
    runner = FakeRunner(bus=bus, delay=0.0)
    req = RunRequest(
        run_id="run-fake-1",
        ticker="AAPL",
        analysis_date=date(2026, 4, 25),
        analysts=["market", "news"],
        debate_rounds=1,
        llm_provider="openai",
        llm_deep_model="gpt-x",
        llm_quick_model="gpt-x-mini",
    )

    result = await runner.run(req)

    types = [e.type for e in bus.history("run-fake-1")]
    assert "agent_message" in types
    assert "progress" in types
    assert types[-1] == "done"
    assert result.decision == "BUY"
    assert result.final_state["market_report"].startswith("Fake market report")


async def test_fake_runner_finishes_bus():
    bus = EventBus()
    runner = FakeRunner(bus=bus, delay=0.0)
    req = RunRequest(
        run_id="run-fake-2",
        ticker="AAPL",
        analysis_date=date(2026, 4, 25),
        analysts=["market"],
        debate_rounds=1,
        llm_provider="openai",
        llm_deep_model="gpt-x",
        llm_quick_model="gpt-x-mini",
    )
    await runner.run(req)
    assert bus.is_finished("run-fake-2")


def test_extract_decision_word_boundaries():
    assert _extract_decision("BUYING OPPORTUNITY") is None
    assert _extract_decision("HOUSEHOLD goods") is None
    assert _extract_decision("BUY now") == "BUY"
    assert _extract_decision("Final: HOLD.") == "HOLD"
    assert _extract_decision("recommend SELL") == "SELL"
    assert _extract_decision("nothing relevant") is None


async def test_fake_runner_done_event_payload_shape():
    bus = EventBus()
    runner = FakeRunner(bus=bus, delay=0.0)
    req = RunRequest(
        run_id="run-fake-shape",
        ticker="AAPL",
        analysis_date=date(2026, 4, 25),
        analysts=["market"],
        debate_rounds=1,
        llm_provider="openai",
        llm_deep_model="gpt-x",
        llm_quick_model="gpt-x-mini",
    )
    await runner.run(req)
    done_events = [e for e in bus.history("run-fake-shape") if e.type == "done"]
    assert len(done_events) == 1
    payload = done_events[0].data
    assert payload["decision"] == "BUY"
    assert payload["confidence"] == 0.78
