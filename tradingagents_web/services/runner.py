"""Runner protocol + fake/real implementations.

The runner consumes a RunRequest, emits AnalysisEvents on the bus, and returns a
RunResult capturing the final state. The API layer persists the result to DB.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Awaitable, Callable, Protocol

from tradingagents_web.services.event_bus import AnalysisEvent, EventBus

logger = logging.getLogger(__name__)

ConfidenceJudge = Callable[["RunRequest", dict[str, Any]], Awaitable[float | None]]


PHASE_ORDER: tuple[str, ...] = ("analyst", "research", "trader", "risk")
PHASE_LABELS: dict[str, str] = {
    "analyst": "애널리스트 분석",
    "research": "리서치 토론",
    "trader": "트레이더 결정",
    "risk": "리스크 검토",
}
PHASE_TOTAL: int = len(PHASE_ORDER)

_NODE_TO_PHASE: dict[str, str] = {
    "Market Analyst": "analyst",
    "Social Analyst": "analyst",
    "News Analyst": "analyst",
    "Fundamentals Analyst": "analyst",
    "Bull Researcher": "research",
    "Bear Researcher": "research",
    "Research Manager": "research",
    "Trader": "trader",
    "Aggressive Analyst": "risk",
    "Neutral Analyst": "risk",
    "Conservative Analyst": "risk",
    "Portfolio Manager": "risk",
}


def _phase_for_node(node: str) -> str | None:
    """Map a LangGraph node name to its analysis phase.

    Phases (analyst → research → trader → risk) collapse the granular
    ToolNode/Msg-Clear iterations of each agent into a single user-facing
    progress step, so the UI shows 4 deterministic stages instead of an
    ever-growing N/N counter.

    Args:
        node: Node name as emitted by LangGraph stream chunks.

    Returns:
        One of ``"analyst" | "research" | "trader" | "risk"``, or ``None``
        if the node is unrecognised (callers should ignore in that case).
    """
    if node in _NODE_TO_PHASE:
        return _NODE_TO_PHASE[node]
    if node.startswith("tools_") or node.startswith("Msg Clear "):
        return "analyst"
    return None


def _progress_payload(phase: str) -> dict[str, Any]:
    """Build the SSE ``progress`` event payload for a phase transition.

    Args:
        phase: Phase key (must be in :data:`PHASE_ORDER`).

    Returns:
        Payload dict with ``step``/``total`` (kept for backwards compat with
        the existing UI gauge) plus ``phase``/``phase_label`` for the new
        phase-based progress display.
    """
    index = PHASE_ORDER.index(phase) + 1
    return {
        "step": index,
        "total": PHASE_TOTAL,
        "phase": phase,
        "phase_label": PHASE_LABELS[phase],
    }


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
        confidence: Confidence score in [0, 1], or None if the judge was
            disabled, the LLM call failed, or the response was unparseable.
        final_state: Full LangGraph final state dict (or fake equivalent).
        cost_usd: Estimated API cost in USD, or None (not yet tracked).
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
        # (role, phase, text_template) — {tk} is substituted with ticker
        steps: list[tuple[str, str, str]] = [
            ("market", "analyst", "Fake market report for {tk}"),
            ("social", "analyst", "Fake social sentiment for {tk}"),
            ("news", "analyst", "Fake news summary for {tk}"),
            ("fundamentals", "analyst", "Fake fundamentals for {tk}"),
            (
                "research",
                "research",
                "Bull/Bear debate concluded — buy thesis stronger",
            ),
            ("trader", "trader", "Recommend BUY with conviction 0.78"),
            ("risk", "risk", "Risk team aligned: BUY"),
        ]
        # Keep analyst-specific steps that were requested, plus fixed closing steps
        active = [s for s in steps if s[0] in request.analysts] + steps[-3:]

        try:
            current_phase: str | None = None
            for role, phase, text in active:
                self.bus.publish(
                    rid,
                    AnalysisEvent(
                        type="agent_message",
                        data={"role": role, "text": text.format(tk=request.ticker)},
                    ),
                )
                if phase != current_phase:
                    current_phase = phase
                    self.bus.publish(
                        rid,
                        AnalysisEvent(
                            type="progress",
                            data=_progress_payload(phase),
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

    After the graph completes, an LLM-as-judge step is invoked to score
    the run's confidence in [0, 1]. The judge is a separate, isolated
    LLM call (see :func:`_llm_confidence_judge`) and any failure results
    in ``confidence=None`` without affecting the main run. Disable
    globally via ``WEB_CONFIDENCE_JUDGE=false``.

    Args:
        bus: The EventBus to publish events to.
        judge: Optional confidence judge override. Defaults to
            :func:`_llm_confidence_judge`. Tests inject stubs here.
    """

    def __init__(
        self,
        bus: EventBus,
        *,
        judge: ConfidenceJudge | None = None,
    ) -> None:
        self.bus = bus
        self.judge: ConfidenceJudge = judge or _llm_confidence_judge

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
            current_phase: str | None = None
            for chunk in graph_obj.graph.stream(init_state, **stream_args):
                # updates mode: chunk is {node_name: state_delta}
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
                    phase = _phase_for_node(node)
                    if phase is not None and phase != current_phase:
                        current_phase = phase
                        _publish_threadsafe(
                            AnalysisEvent(
                                type="progress",
                                data=_progress_payload(phase),
                            ),
                        )

            return accumulated

        try:
            final_state = await asyncio.to_thread(_build_and_stream)
            decision_text = str(final_state.get("final_trade_decision") or "")
            decision = _extract_decision(decision_text)
            safe_final_state = _json_safe_final_state(final_state)

            confidence = await _safe_judge(self.judge, request, final_state)

            # This publish is on the event-loop thread, so call directly.
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
                final_state=safe_final_state,
            )
        except Exception as exc:
            logger.exception("Real runner failed for run_id=%s", rid)
            self.bus.publish(
                rid, AnalysisEvent(type="error", data={"message": str(exc)})
            )
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


_DECISION_KEYWORDS: tuple[str, ...] = (
    "BUY",
    "OVERWEIGHT",
    "HOLD",
    "UNDERWEIGHT",
    "SELL",
)


def _extract_decision(text: str) -> str | None:
    """Extract a canonical trade decision keyword from free-form text.

    The portfolio manager prompt requires the response to start with a
    ``**Rating**: <X>`` header where ``<X>`` is one of Buy / Overweight /
    Hold / Underweight / Sell. Anchor the match to that header first, since
    the body of the response routinely references all five labels while
    summarising the analyst debate (e.g. "단순 Hold보다 Sell이 적절").

    Args:
        text: The raw ``final_trade_decision`` value from the graph state.

    Returns:
        One of "BUY", "OVERWEIGHT", "HOLD", "UNDERWEIGHT", "SELL", or None.
    """
    upper = text.upper()
    keyword_alt = "|".join(_DECISION_KEYWORDS)

    # Prefer the structured "Rating: <X>" header. ``[^A-Z0-9]`` keeps the
    # gap permissive (asterisks, colons, whitespace) while disallowing other
    # alphanumeric tokens like "SCALE" between the header and the keyword.
    rating_match = re.search(
        rf"\bRATING\b[^A-Z0-9]{{0,10}}({keyword_alt})\b",
        upper,
    )
    if rating_match:
        return rating_match.group(1)

    # Fallback: earliest keyword wins. Iterating in priority order and
    # returning on first hit (the previous behaviour) misclassified texts
    # whose Rating was Sell but body mentioned Hold or Buy first.
    earliest: tuple[int, str] | None = None
    for word in _DECISION_KEYWORDS:
        m = re.search(rf"\b{word}\b", upper)
        if m and (earliest is None or m.start() < earliest[0]):
            earliest = (m.start(), word)
    return earliest[1] if earliest else None


# --- Confidence judge ------------------------------------------------------


_JUDGE_SYSTEM_PROMPT = (
    "당신은 트레이딩 분석 결과의 신뢰도를 평가하는 심사관입니다.\n"
    "여러 애널리스트의 토론과 최종 결정을 보고, 그 결정에 대한 신뢰도를 "
    "0.0~1.0 사이 부동소수점으로 채점하세요.\n"
    "- 1.0: 모든 애널리스트가 동의하고 근거가 매우 견고함\n"
    "- 0.5: 동전 던지기 수준 (찬반이 균형)\n"
    "- 0.0: 결론에 강한 모순이 있거나 근거가 약함\n"
    "응답은 반드시 다음 JSON 한 줄로만 출력합니다(추가 텍스트 금지):\n"
    '{"confidence": 0.0, "rationale": "한 문장 요약"}'
)

_JUDGE_SECTION_LIMIT = 4000
_JUDGE_RISK_SECTION_LIMIT = 2000


async def _safe_judge(
    judge: ConfidenceJudge,
    request: RunRequest,
    final_state: dict[str, Any],
) -> float | None:
    """Invoke a confidence judge, swallowing all errors to None.

    The main run must never fail because of a judge problem. This helper
    centralises the safety net so call sites stay clean.
    """
    try:
        value = await judge(request, final_state)
    except Exception:
        logger.warning(
            "Confidence judge raised for run_id=%s", request.run_id, exc_info=True
        )
        return None
    if value is None:
        return None
    if not isinstance(value, int | float):
        return None
    return _clamp_unit(float(value))


async def _llm_confidence_judge(
    request: RunRequest, final_state: dict[str, Any]
) -> float | None:
    """Default judge: ask the quick-think LLM to score [0, 1] confidence.

    Disabled when ``WEB_CONFIDENCE_JUDGE`` env is falsy. Returns None on
    any failure (LLM error, parse failure, missing key). Cost is one
    additional quick-model call per run.
    """
    if not _is_judge_enabled():
        return None
    try:
        return await asyncio.to_thread(_invoke_judge_sync, request, final_state)
    except Exception:
        logger.warning(
            "Default confidence judge failed for run_id=%s",
            request.run_id,
            exc_info=True,
        )
        return None


def _is_judge_enabled() -> bool:
    raw = os.getenv("WEB_CONFIDENCE_JUDGE", "true").strip().lower()
    return raw not in {"0", "false", "no", "off", ""}


def _invoke_judge_sync(
    request: RunRequest, final_state: dict[str, Any]
) -> float | None:
    """Synchronous LLM call. Run via ``asyncio.to_thread``."""
    from langchain_core.messages import HumanMessage, SystemMessage

    from tradingagents.llm_clients import create_llm_client

    client = create_llm_client(
        provider=request.llm_provider, model=request.llm_deep_model
    )
    llm = client.get_llm()
    messages = [
        SystemMessage(content=_JUDGE_SYSTEM_PROMPT),
        HumanMessage(content=_build_judge_prompt(final_state)),
    ]
    response = llm.invoke(messages)
    text = _normalize_llm_text(getattr(response, "content", ""))
    return _parse_confidence(text)


def _build_judge_prompt(final_state: dict[str, Any]) -> str:
    sections: list[str] = []
    for key, label in (
        ("final_trade_decision", "최종 결정"),
        ("trader_investment_plan", "트레이더 계획"),
        ("investment_plan", "투자 의견"),
    ):
        value = final_state.get(key)
        if isinstance(value, str) and value.strip():
            sections.append(f"## {label}\n{value[:_JUDGE_SECTION_LIMIT]}")
    risk = final_state.get("risk_debate_state")
    if isinstance(risk, dict):
        for key in (
            "aggressive_history",
            "conservative_history",
            "neutral_history",
            "judge_decision",
        ):
            value = risk.get(key)
            if isinstance(value, str) and value.strip():
                sections.append(f"## risk:{key}\n{value[:_JUDGE_RISK_SECTION_LIMIT]}")
    return "\n\n".join(sections) if sections else "분석 결과 없음"


def _normalize_llm_text(content: Any) -> str:
    """Flatten LangChain content (str or list of typed blocks) to a string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)
    return str(content) if content is not None else ""


def _parse_confidence(text: str) -> float | None:
    """Extract a [0, 1] confidence score from a free-form LLM response.

    Tries, in order:
    1. JSON object with a numeric ``confidence`` key.
    2. A trailing ``XX%`` percentage (interpreted as XX/100).
    3. The first plausible 0..1 float.
    Returns None when none of the strategies yield a numeric value.
    """
    if not text:
        return None

    # 1) JSON object — search for the first {...} block. Use a non-greedy
    #    body match to tolerate extra content surrounding the JSON.
    for json_match in re.finditer(r"\{.*?\}", text, flags=re.DOTALL):
        try:
            payload = json.loads(json_match.group(0))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and "confidence" in payload:
            value = payload["confidence"]
            if isinstance(value, bool):  # bool is an int subclass — exclude
                return None
            if isinstance(value, int | float):
                return _clamp_unit(float(value))
            return None

    # 2) Percentage like "78%".
    pct = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%", text)
    if pct:
        try:
            return _clamp_unit(float(pct.group(1)) / 100.0)
        except ValueError:
            pass

    # 3) First plausible 0..1 float anywhere in the text.
    num = re.search(r"\b(?:0?\.\d+|1(?:\.0+)?)\b", text)
    if num:
        try:
            return _clamp_unit(float(num.group(0)))
        except ValueError:
            pass

    return None


def _clamp_unit(value: float) -> float | None:
    """Return value clamped to [0, 1]; None for NaN/inf."""
    if math.isnan(value) or math.isinf(value):
        return None
    return max(0.0, min(1.0, value))
