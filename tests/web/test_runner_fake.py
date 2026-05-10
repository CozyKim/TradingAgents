"""Fake runner emits a deterministic event sequence for tests/dev."""
import sys
import types
from collections.abc import Iterator
from datetime import date
from typing import Any

from tradingagents_web.services.event_bus import EventBus
from tradingagents_web.services.runner import (
    PHASE_LABELS,
    PHASE_ORDER,
    PHASE_TOTAL,
    FakeRunner,
    RealRunner,
    RunRequest,
    _extract_decision,
    _json_safe_final_state,
    _llm_confidence_judge,
    _parse_confidence,
    _phase_for_node,
)


def _make_real_runner_request(run_id: str = "run-real") -> RunRequest:
    return RunRequest(
        run_id=run_id,
        ticker="AAPL",
        analysis_date=date(2026, 4, 25),
        analysts=["market"],
        debate_rounds=1,
        llm_provider="openai",
        llm_deep_model="gpt-x",
        llm_quick_model="gpt-x-mini",
    )


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
        yield {
            "Trader": {"trader_investment_plan": "Open AAPL with conviction"}
        }
        yield {
            "Portfolio Manager": {
                "final_trade_decision": "**Rating**: Buy\n근거 견고"
            }
        }


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


def _install_fake_graph(monkeypatch) -> None:
    fake_module = types.ModuleType("tradingagents.graph.trading_graph")
    setattr(fake_module, "TradingAgentsGraph", _FakeTradingAgentsGraph)
    monkeypatch.setitem(
        sys.modules, "tradingagents.graph.trading_graph", fake_module
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


def test_extract_decision_rating_header_wins_over_body_mentions():
    # Reproduces the regression where the body referenced Hold/Buy while
    # the actual Rating was Sell.
    text = (
        "1. **Rating**: **Sell**\n\n"
        "2. **Executive Summary**:\n"
        "GOOGL에 대한 최종 결정은 **Sell**입니다.\n"
        "중립 애널리스트의 Hold 논리는 균형적이지만 단순 Hold보다 적극적 축소가 적절합니다.\n"
        "공격적 애널리스트가 Buy를 주장했으나 받아들이지 않습니다.\n"
    )
    assert _extract_decision(text) == "SELL"


def test_extract_decision_rating_header_handles_alt_formats():
    assert _extract_decision("## 1. **Rating: Hold**\n\n매수/매도/보유 논의...") == "HOLD"
    assert _extract_decision("**Rating**: Overweight\n\nBuy 신호도 일부 존재") == "OVERWEIGHT"
    assert _extract_decision("Rating:    Underweight — 추가 매수 자제") == "UNDERWEIGHT"


def test_extract_decision_falls_back_to_earliest_when_no_header():
    # Without a Rating header, pick whichever decision keyword comes first.
    assert _extract_decision("We recommend SELL given valuation. Some considered Hold.") == "SELL"
    assert _extract_decision("HOLD for now, do not BUY at these levels.") == "HOLD"


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


async def _stub_judge_none(_req: RunRequest, _state: dict[str, Any]) -> None:
    return None


async def test_real_runner_emits_phase_progress_in_order(monkeypatch):
    _install_fake_graph(monkeypatch)

    bus = EventBus()
    runner = RealRunner(bus=bus, judge=_stub_judge_none)
    req = _make_real_runner_request("run-real-progress")

    await runner.run(req)

    progress_events = [
        event for event in bus.history("run-real-progress") if event.type == "progress"
    ]
    # _FakeGraph yields one node per phase (Market Analyst → Research Manager
    # → Trader → Portfolio Manager), so we expect exactly one progress event
    # per phase, in declared phase order.
    assert [event.data["phase"] for event in progress_events] == list(PHASE_ORDER)
    for event in progress_events:
        assert event.data["total"] == PHASE_TOTAL
        assert event.data["phase_label"] == PHASE_LABELS[event.data["phase"]]
        assert 1 <= event.data["step"] <= PHASE_TOTAL


def test_phase_for_node_covers_all_known_nodes():
    # Analyst phase: explicit nodes + tools_/Msg Clear prefixes
    assert _phase_for_node("Market Analyst") == "analyst"
    assert _phase_for_node("Fundamentals Analyst") == "analyst"
    assert _phase_for_node("tools_market") == "analyst"
    assert _phase_for_node("Msg Clear News") == "analyst"
    # Research, trader, risk
    assert _phase_for_node("Bull Researcher") == "research"
    assert _phase_for_node("Research Manager") == "research"
    assert _phase_for_node("Trader") == "trader"
    assert _phase_for_node("Aggressive Analyst") == "risk"
    assert _phase_for_node("Portfolio Manager") == "risk"
    # Unknown nodes return None so the runner can ignore them.
    assert _phase_for_node("Unknown Node") is None


async def test_real_runner_uses_injected_judge_for_done_payload(monkeypatch):
    _install_fake_graph(monkeypatch)

    captured: dict[str, Any] = {}

    async def _stub_judge(req: RunRequest, state: dict[str, Any]) -> float:
        captured["request"] = req
        captured["state_keys"] = sorted(state.keys())
        return 0.85

    bus = EventBus()
    runner = RealRunner(bus=bus, judge=_stub_judge)
    req = _make_real_runner_request("run-real-judge")

    result = await runner.run(req)

    done_events = [e for e in bus.history("run-real-judge") if e.type == "done"]
    assert len(done_events) == 1
    assert done_events[0].data["confidence"] == 0.85
    assert done_events[0].data["decision"] == "BUY"
    assert result.confidence == 0.85
    assert captured["request"].run_id == "run-real-judge"
    # judge sees the accumulated final_state, including reports we yielded.
    assert "final_trade_decision" in captured["state_keys"]


async def test_real_runner_judge_failure_yields_none_confidence(monkeypatch):
    _install_fake_graph(monkeypatch)

    async def _broken_judge(_req: RunRequest, _state: dict[str, Any]) -> float:
        raise RuntimeError("judge boom")

    bus = EventBus()
    runner = RealRunner(bus=bus, judge=_broken_judge)
    req = _make_real_runner_request("run-real-judge-fail")

    result = await runner.run(req)

    # Run completes successfully despite judge error.
    done_events = [e for e in bus.history("run-real-judge-fail") if e.type == "done"]
    assert len(done_events) == 1
    assert done_events[0].data["confidence"] is None
    assert result.confidence is None
    assert result.decision == "BUY"


async def test_default_judge_disabled_via_env(monkeypatch):
    monkeypatch.setenv("WEB_CONFIDENCE_JUDGE", "false")
    req = _make_real_runner_request("run-real-judge-disabled")
    value = await _llm_confidence_judge(req, {"final_trade_decision": "BUY"})
    assert value is None


async def test_default_judge_parses_llm_response(monkeypatch):
    monkeypatch.setenv("WEB_CONFIDENCE_JUDGE", "true")

    class _Resp:
        content = '{"confidence": 0.72, "rationale": "분석가 다수 동의"}'

    class _FakeLLM:
        def invoke(self, _messages: list[Any]) -> _Resp:
            return _Resp()

    class _FakeClient:
        def get_llm(self) -> _FakeLLM:
            return _FakeLLM()

    fake_factory = types.ModuleType("tradingagents.llm_clients")

    def _create_llm_client(provider: str, model: str, **_: Any) -> _FakeClient:
        assert provider == "openai"
        assert model == "gpt-x-mini"
        return _FakeClient()

    fake_factory.create_llm_client = _create_llm_client
    monkeypatch.setitem(sys.modules, "tradingagents.llm_clients", fake_factory)

    req = _make_real_runner_request("run-real-judge-default")
    value = await _llm_confidence_judge(
        req,
        {
            "final_trade_decision": "Rating: Buy",
            "trader_investment_plan": "Open position",
        },
    )
    assert value == 0.72


async def test_default_judge_returns_none_when_llm_raises(monkeypatch):
    monkeypatch.setenv("WEB_CONFIDENCE_JUDGE", "true")

    class _ExplodingClient:
        def get_llm(self):
            raise RuntimeError("no api key")

    fake_factory = types.ModuleType("tradingagents.llm_clients")
    fake_factory.create_llm_client = lambda *_a, **_k: _ExplodingClient()
    monkeypatch.setitem(sys.modules, "tradingagents.llm_clients", fake_factory)

    req = _make_real_runner_request("run-real-judge-explode")
    value = await _llm_confidence_judge(req, {"final_trade_decision": "BUY"})
    assert value is None


def test_parse_confidence_json_object():
    assert _parse_confidence('{"confidence": 0.42}') == 0.42
    assert _parse_confidence(
        'pre {"confidence": 0.9, "rationale": "x"} post'
    ) == 0.9


def test_parse_confidence_clamps_out_of_range():
    assert _parse_confidence('{"confidence": 1.4}') == 1.0
    assert _parse_confidence('{"confidence": -0.3}') == 0.0


def test_parse_confidence_percent_fallback():
    # No JSON; "78%" should be interpreted as 0.78.
    assert _parse_confidence("Final confidence: 78%") == 0.78


def test_parse_confidence_float_fallback():
    # No JSON, no percent; first plausible 0..1 float wins.
    assert _parse_confidence("Score: 0.55 (medium conviction)") == 0.55


def test_parse_confidence_returns_none_when_unparseable():
    assert _parse_confidence("") is None
    assert _parse_confidence("nothing relevant here") is None
    assert _parse_confidence('{"confidence": "high"}') is None


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
