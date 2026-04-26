"""Runner protocol + fake/real implementations.

The runner consumes a RunRequest, emits AnalysisEvents on the bus, and returns a
RunResult capturing the final state. The API layer persists the result to DB.
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol

from tradingagents_web.services.event_bus import AnalysisEvent, EventBus

logger = logging.getLogger(__name__)


@dataclass
class RunRequest:
    """Request payload describing a single analysis run.

    Attributes:
        run_id: Unique identifier for this run (UUID string).
        ticker: Stock ticker symbol (e.g. "AAPL").
        analysis_date: The date to run analysis for.
        analysts: List of analyst roles to activate (e.g. ["market", "news"]).
        debate_rounds: Number of bull/bear debate rounds.
        llm_provider: LLM provider name (e.g. "openai").
        llm_deep_model: Model ID used for deep-think operations.
        llm_quick_model: Model ID used for quick-think operations.
        extra_config: Optional extra key-value pairs forwarded to the graph config.
    """

    run_id: str
    ticker: str
    analysis_date: date
    analysts: list[str]
    debate_rounds: int
    llm_provider: str
    llm_deep_model: str
    llm_quick_model: str
    extra_config: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunResult:
    """Result returned by a completed runner.

    Attributes:
        decision: Final trade decision string (e.g. "BUY", "SELL", "HOLD").
        confidence: Confidence score in [0, 1], or None if not captured.
        final_state: Full LangGraph final state dict (or fake equivalent).
        cost_usd: Estimated API cost in USD, or None (tracked in M5+).
    """

    decision: str | None
    confidence: float | None
    final_state: dict[str, Any]
    cost_usd: float | None = None


class Runner(Protocol):
    """Protocol for all runner implementations.

    Both FakeRunner and RealRunner must satisfy this interface. The API layer
    calls ``runner.run(request)`` and awaits the result.
    """

    async def run(self, request: RunRequest) -> RunResult:
        """Execute an analysis run and return the result.

        Args:
            request: Fully populated RunRequest describing the run.

        Returns:
            RunResult containing the final decision and state.
        """
        ...


class FakeRunner:
    """Emits a deterministic event sequence. No LLM calls.

    Used by tests and development environments to exercise the full
    event pipeline without incurring LLM costs. The event sequence
    shape (agent_message + progress per step, done at the end) matches
    what the SSE endpoint and frontend hooks expect.

    Args:
        bus: The EventBus to publish events to.
        delay: Seconds to sleep between steps (0.0 for tests).

    Example:
        >>> bus = EventBus()
        >>> runner = FakeRunner(bus=bus, delay=0.0)
        >>> result = await runner.run(req)
        >>> assert result.decision == "BUY"
    """

    def __init__(self, bus: EventBus, delay: float = 0.05) -> None:
        self.bus = bus
        self.delay = delay

    async def run(self, request: RunRequest) -> RunResult:
        """Run the fake analysis and emit deterministic events.

        Emits ``agent_message`` + ``progress`` per active step, then a
        ``done`` event. Always returns BUY with confidence 0.78.

        Args:
            request: The run request (only ``run_id``, ``ticker``, and
                ``analysts`` are used by the fake implementation).

        Returns:
            RunResult with decision="BUY" and confidence=0.78.
        """
        rid = request.run_id
        # (role, text_template) — {tk} is substituted with ticker
        steps = [
            ("market", "Fake market report for {tk}"),
            ("social", "Fake social sentiment for {tk}"),
            ("news", "Fake news summary for {tk}"),
            ("fundamentals", "Fake fundamentals for {tk}"),
            ("research", "Bull/Bear debate concluded — buy thesis stronger"),
            ("trader", "Recommend BUY with conviction 0.78"),
            ("risk", "Risk team aligned: BUY"),
        ]
        # Keep analyst-specific steps that were requested, plus fixed closing steps
        active = [s for s in steps if s[0] in request.analysts] + steps[-3:]
        total = len(active)

        try:
            for i, (role, text) in enumerate(active, start=1):
                self.bus.publish(
                    rid,
                    AnalysisEvent(
                        type="agent_message",
                        data={"role": role, "text": text.format(tk=request.ticker)},
                    ),
                )
                self.bus.publish(
                    rid,
                    AnalysisEvent(
                        type="progress",
                        data={"step": i, "total": total},
                    ),
                )
                if self.delay:
                    await asyncio.sleep(self.delay)

            final_state: dict[str, Any] = {
                "market_report": f"Fake market report for {request.ticker}",
                "sentiment_report": f"Fake sentiment for {request.ticker}",
                "news_report": f"Fake news for {request.ticker}",
                "fundamentals_report": f"Fake fundamentals for {request.ticker}",
                "investment_plan": "BUY thesis is stronger than bear case",
                "trader_investment_plan": f"Open position in {request.ticker}",
                "final_trade_decision": "BUY",
            }
            decision = "BUY"
            confidence = 0.78

            self.bus.publish(
                rid,
                AnalysisEvent(
                    type="done",
                    data={"decision": decision, "confidence": confidence},
                ),
            )
            return RunResult(
                decision=decision,
                confidence=confidence,
                final_state=final_state,
            )
        finally:
            # Always mark the run as finished, even if an error occurs
            self.bus.finish(rid)


class RealRunner:
    """Drives the actual TradingAgentsGraph and streams node outputs.

    Uses ``asyncio.to_thread`` to run the synchronous LangGraph stream
    off the event loop so it does not block async handlers.

    Note:
        ``confidence`` is always None in this implementation. Cost/token
        tracking is deferred to M5.

    Args:
        bus: The EventBus to publish events to.
    """

    def __init__(self, bus: EventBus) -> None:
        self.bus = bus

    async def run(self, request: RunRequest) -> RunResult:
        """Stream the TradingAgentsGraph and emit events for each node output.

        Lazy-imports ``tradingagents`` inside the method to avoid loading
        LangGraph when tests use FakeRunner.

        Args:
            request: Fully populated RunRequest.

        Returns:
            RunResult with the final graph state and extracted decision.

        Raises:
            Exception: Re-raises any exception after publishing an ``error``
                event and finishing the bus for this run.
        """
        # Lazy import: keeps web tests fast and avoids loading langgraph for unit tests.
        from tradingagents.default_config import DEFAULT_CONFIG
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        config = dict(DEFAULT_CONFIG)
        config["llm_provider"] = request.llm_provider
        config["deep_think_llm"] = request.llm_deep_model
        config["quick_think_llm"] = request.llm_quick_model
        config["max_debate_rounds"] = request.debate_rounds
        config.update(request.extra_config)

        rid = request.run_id
        loop = asyncio.get_running_loop()
        estimated_total = _estimate_total_steps(request, config)

        def _publish_threadsafe(event: AnalysisEvent) -> None:
            """Schedule a bus.publish on the event loop from a worker thread."""
            loop.call_soon_threadsafe(self.bus.publish, rid, event)

        def _build_and_stream() -> dict[str, Any]:
            """Synchronous helper executed in a thread pool via to_thread."""
            graph_obj = TradingAgentsGraph(
                selected_analysts=request.analysts,
                debug=False,
                config=config,
            )
            init_state = graph_obj.propagator.create_initial_state(
                request.ticker, str(request.analysis_date)
            )
            # Clone args and override stream_mode to "updates" so each chunk is
            # {node_name: state_delta} rather than the full cumulative state.
            stream_args = dict(graph_obj.propagator.get_graph_args())
            stream_args["stream_mode"] = "updates"

            accumulated: dict[str, Any] = dict(init_state)
            step = 0
            for chunk in graph_obj.graph.stream(init_state, **stream_args):
                # updates mode: chunk is {node_name: state_delta}
                step += 1
                for node, delta in chunk.items():
                    if isinstance(delta, dict):
                        accumulated.update(delta)
                    text = _summarize_delta(delta)
                    if text:
                        _publish_threadsafe(
                            AnalysisEvent(
                                type="agent_message",
                                data={"role": node, "text": text},
                            ),
                        )
                _publish_threadsafe(
                    AnalysisEvent(
                        type="progress",
                        data={"step": step, "total": max(estimated_total, step)},
                    ),
                )

            return accumulated

        try:
            final_state = await asyncio.to_thread(_build_and_stream)
            decision_text = str(final_state.get("final_trade_decision") or "")
            decision = _extract_decision(decision_text)
            safe_final_state = _json_safe_final_state(final_state)

            # This publish is on the event-loop thread, so call directly.
            self.bus.publish(
                rid,
                AnalysisEvent(
                    type="done",
                    data={"decision": decision, "confidence": None},
                ),
            )
            return RunResult(
                decision=decision,
                confidence=None,
                final_state=safe_final_state,
            )
        except Exception as exc:
            logger.exception("Real runner failed for run_id=%s", rid)
            self.bus.publish(rid, AnalysisEvent(type="error", data={"message": str(exc)}))
            raise
        finally:
            self.bus.finish(rid)


def _summarize_delta(delta: Any) -> str:
    """Pull the most recent message text out of a LangGraph state delta.

    Args:
        delta: A single node's state delta from a LangGraph stream chunk.

    Returns:
        A truncated string representation, or empty string if nothing useful
        was found.
    """
    if not isinstance(delta, dict):
        return ""
    msgs = delta.get("messages")
    if msgs:
        last = msgs[-1]
        return getattr(last, "content", str(last))[:4000]
    for key in (
        "market_report",
        "sentiment_report",
        "news_report",
        "fundamentals_report",
        "investment_plan",
        "trader_investment_plan",
        "final_trade_decision",
    ):
        if delta.get(key):
            return f"[{key}] {str(delta[key])[:4000]}"
    return ""


def _estimate_total_steps(request: RunRequest, config: dict[str, Any]) -> int:
    """Estimate the minimum number of graph stream updates for progress UI.

    The real LangGraph can emit extra updates when analyst tool loops run, so
    this is intentionally a lower-bound estimate rather than an exact promise.
    The caller clamps the total upward if actual streamed steps exceed it.

    Args:
        request: Run request containing selected analysts and debate rounds.
        config: Effective TradingAgents graph configuration.

    Returns:
        Positive estimated total step count for progress events.
    """
    analyst_steps = max(1, len(request.analysts)) * 2
    debate_rounds = _positive_int(
        config.get("max_debate_rounds"), default=request.debate_rounds
    )
    risk_rounds = _positive_int(config.get("max_risk_discuss_rounds"), default=1)

    research_steps = (2 * debate_rounds) + 1  # bull/bear turns + manager
    trader_steps = 1
    risk_steps = (3 * risk_rounds) + 1  # aggressive/conservative/neutral + manager
    return analyst_steps + research_steps + trader_steps + risk_steps


def _positive_int(value: Any, *, default: int) -> int:
    """Return a positive integer parsed from value, falling back to default.

    Args:
        value: Candidate value from runtime config.
        default: Positive fallback value.

    Returns:
        A positive integer.
    """
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(1, parsed)


def _json_safe_final_state(state: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-serializable copy of a graph final state.

    LangGraph states can contain LangChain message objects and typed tuples.
    The database stores this payload in a JSON column, so non-JSON objects must
    be simplified while preserving the report fields used by history screens.

    Args:
        state: Raw final state returned by the runner.

    Returns:
        JSON-serializable copy of the final state.
    """
    return {str(key): _json_safe_value(value) for key, value in state.items()}


def _json_safe_value(value: Any) -> Any:
    """Convert a value into a JSON-serializable structure.

    Args:
        value: Arbitrary value from graph state.

    Returns:
        A value composed of JSON scalars, lists, and dictionaries.
    """
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe_value(item) for item in value]

    content = getattr(value, "content", None)
    if isinstance(content, str):
        return content
    if content is not None:
        return _json_safe_value(content)

    return str(value)


def _extract_decision(text: str) -> str | None:
    """Extract a canonical trade decision keyword from free-form text.

    Uses word-boundary matching so that substrings like "BUYING" or "HOUSEHOLD"
    do not false-match "BUY" or "HOLD".

    Args:
        text: The raw ``final_trade_decision`` value from the graph state.

    Returns:
        One of "BUY", "OVERWEIGHT", "HOLD", "UNDERWEIGHT", "SELL", or None.
    """
    upper = text.upper()
    for word in ("BUY", "OVERWEIGHT", "HOLD", "UNDERWEIGHT", "SELL"):
        if re.search(rf"\b{word}\b", upper):
            return word
    return None
