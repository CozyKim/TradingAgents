"""Fake runner emits a deterministic event sequence for tests/dev."""
import sys
import types
from collections.abc import Iterator
from datetime import date
from typing import Any

from tradingagents_web.services.event_bus import EventBus
from tradingagents_web.services.runner import (
    FakeRunner,
    RealRunner,
    RunRequest,
    _extract_decision,
    _json_safe_final_state,
)


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


async def test_real_runner_emits_progress_with_estimated_total(monkeypatch):
    class _FakePropagator:
        def create_initial_state(
            self, company_name: str, trade_date: str
        ) -> dict[str, str]:
            return {"company_of_interest": company_name, "trade_date": trade_date}

        def get_graph_args(self) -> dict[str, Any]:
            return {}

    class _FakeGraph:
        def stream(
            self,
            _init_state: dict[str, str],
            **_kwargs: object,
        ) -> Iterator[dict[str, dict[str, str]]]:
            yield {"Market Analyst": {"market_report": "market ok"}}
            yield {"Research Manager": {"investment_plan": "plan ok"}}
            yield {"Portfolio Manager": {"final_trade_decision": "BUY"}}

    class _FakeTradingAgentsGraph:
        def __init__(
            self,
            selected_analysts: list[str],
            debug: bool,
            config: dict[str, Any],
        ) -> None:
            self.selected_analysts = selected_analysts
            self.debug = debug
            self.config = config
            self.propagator = _FakePropagator()
            self.graph = _FakeGraph()

    fake_module = types.ModuleType("tradingagents.graph.trading_graph")
    fake_module.TradingAgentsGraph = _FakeTradingAgentsGraph
    monkeypatch.setitem(sys.modules, "tradingagents.graph.trading_graph", fake_module)

    bus = EventBus()
    runner = RealRunner(bus=bus)
    req = RunRequest(
        run_id="run-real-progress",
        ticker="AAPL",
        analysis_date=date(2026, 4, 25),
        analysts=["market"],
        debate_rounds=1,
        llm_provider="openai",
        llm_deep_model="gpt-x",
        llm_quick_model="gpt-x-mini",
    )

    await runner.run(req)

    progress_events = [
        event for event in bus.history("run-real-progress") if event.type == "progress"
    ]
    assert progress_events
    assert all(event.data["total"] > 0 for event in progress_events)


def test_json_safe_final_state_preserves_reports_and_simplifies_messages():
    class _Message:
        content = "agent message"

    state = {
        "messages": [_Message()],
        "market_report": "market ok",
        "nested": {"items": (1, _Message())},
    }

    safe_state = _json_safe_final_state(state)

    assert safe_state["market_report"] == "market ok"
    assert safe_state["messages"] == ["agent message"]
    assert safe_state["nested"] == {"items": [1, "agent message"]}
