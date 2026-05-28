"""Competitive Landscape node — third stage.

Produces a list of companies with structured share/basis/confidence/sources.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from tradingagents.graph_sector.nodes._tool_loop import invoke_with_tool_loop
from tradingagents.graph_sector.state import SectorState
from tradingagents.graph_sector.tools.web_search import SearchBudget, make_web_search_tool

logger = logging.getLogger(__name__)

VALID_BASIS = {"reported", "estimated", "unknown"}
VALID_CONFIDENCE = {"high", "medium", "low"}


SYSTEM_PROMPT = """당신은 산업 분석가다. 주어진 가치사슬 단계별로 **핵심 기업과 점유율**을 정리한다.

각 기업은 다음 JSON 형태로 출력:

{
  "companies": [
    {
      "name": "기업명",
      "ticker": "선택, 모르면 null",
      "stage": "가치사슬 어디 단계인지",
      "share_value": 35.0,
      "share_basis": "reported|estimated|unknown",
      "confidence": "high|medium|low",
      "sources": ["https://..."]
    }
  ]
}

규칙:
- share_basis="reported"는 출처가 명시된 보고서 수치일 때만. 추정이면 "estimated", 근거 없으면 "unknown".
- 점유율 근거 URL은 sources에 반드시 첨부.
- 단계별로 상위 3–5개 기업, 전체 10개 이하.

코드블록 없이 순수 JSON만 출력하라.
"""


def _normalize_company(c: dict) -> dict:
    """Coerce a raw company dict into the schema-stable shape.

    Unknown ``share_basis`` / ``confidence`` values fall back to safe defaults
    rather than raising — the LLM occasionally invents new labels.
    """
    basis = c.get("share_basis", "unknown")
    if basis not in VALID_BASIS:
        basis = "unknown"
    confidence = c.get("confidence", "low")
    if confidence not in VALID_CONFIDENCE:
        confidence = "low"
    # share_value: LLM sometimes returns null, "N/A", "?", "정보 없음" — any
    # non-numeric input collapses to 0.0 AND downgrades basis to "unknown",
    # because a missing number means we no longer trust the basis label either.
    raw_share = c.get("share_value", 0.0)
    if raw_share is None:
        share_value = 0.0
        basis = "unknown"
    else:
        try:
            share_value = float(raw_share)
        except (TypeError, ValueError):
            share_value = 0.0
            basis = "unknown"
    # Out-of-range (negative, >100%): clamp to schema bounds AND mark unknown.
    # CompanyShare Pydantic schema enforces ge=0, le=100, so we must do this
    # here or downstream serialization would 500.
    if share_value < 0.0 or share_value > 100.0:
        share_value = max(0.0, min(100.0, share_value))
        basis = "unknown"
    # sources: LLM sometimes returns a bare URL string, null, or a non-list.
    # Wrap singletons, treat null/non-list as empty so a downstream
    # `list[HttpUrl]` validator doesn't crash and we don't accidentally
    # split a URL into per-character entries. Also drop anything that
    # doesn't look like an http(s) URL — Pydantic HttpUrl will reject those
    # at response-serialization time and 500 the request.
    raw_sources = c.get("sources")
    if isinstance(raw_sources, str):
        sources_iter = [raw_sources]
    elif isinstance(raw_sources, list):
        sources_iter = raw_sources
    else:
        sources_iter = []
    sources_iter = [
        s for s in sources_iter
        if isinstance(s, str) and s.lower().startswith(("http://", "https://"))
    ]
    # ticker: schema says str | None; LLM sometimes returns Korean stock codes
    # as integers (e.g. 5930) or other non-string scalars. Coerce non-None
    # non-strings to str so CompanyShare doesn't reject the report later.
    raw_ticker = c.get("ticker")
    if raw_ticker is None or raw_ticker == "":
        ticker = None
    elif isinstance(raw_ticker, str):
        ticker = raw_ticker
    else:
        ticker = str(raw_ticker)
    return {
        "name": str(c.get("name", "Unknown")),
        "ticker": ticker,
        "stage": str(c.get("stage", "")),
        "share_value": share_value,
        "share_basis": basis,
        "confidence": confidence,
        "sources": [str(u) for u in sources_iter if u],
    }


def _try_parse(content: str) -> list[dict] | None:
    """Parse JSON from raw text, tolerating ```json fences."""
    s = content.strip()
    if s.startswith("```"):
        s = "\n".join(line for line in s.splitlines() if not line.startswith("```"))
    try:
        data = json.loads(s)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    items = data.get("companies")
    if not isinstance(items, list):
        return None
    # Each element must be a dict; bail to retry/fallback if any are scalars.
    # Without this guard _normalize_company would hit AttributeError on c.get().
    if not all(isinstance(c, dict) for c in items):
        return None
    return [_normalize_company(c) for c in items]


def _invoke(chat, tool, messages):
    """Call the model with tool-loop when a tool is bound, else plain invoke."""
    if tool is not None:
        ai, history = invoke_with_tool_loop(chat, tool, messages)
        return ai, history
    ai = chat.invoke(messages)
    return ai, list(messages) + [ai]


def make_competitive_node(llm, budget: SearchBudget | None) -> Callable:
    """Build the competitive_landscape node.

    NOTE on budget lifetime: same closure-capture rule as
    ``make_macro_overview_node`` / ``make_value_chain_node``. The graph must
    be rebuilt per analysis run with a fresh ``SearchBudget``; otherwise
    web_search call counts leak across runs.
    """
    def node(state: SectorState) -> dict[str, Any]:
        tool = None
        if budget is not None:
            budget.current_node = "competitive_landscape"
            tool = make_web_search_tool(budget)
            chat = llm.bind_tools([tool])
        else:
            chat = llm

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=(
                f"산업: {state.sector_name}\n\n"
                f"가치사슬:\n{state.value_chain_md[:3000]}"
            )),
        ]
        ai, history = _invoke(chat, tool, messages)
        raw = ai.content if isinstance(ai.content, str) else str(ai.content)
        parsed = _try_parse(raw)
        if parsed is None:
            # Retry once: ask the model to re-emit JSON only.
            retry_msgs = history + [
                HumanMessage(content="이전 응답이 유효한 JSON이 아니다. JSON만 다시 출력하라."),
            ]
            ai, _ = _invoke(chat, tool, retry_msgs)
            raw = ai.content if isinstance(ai.content, str) else str(ai.content)
            parsed = _try_parse(raw)

        if parsed is None:
            logger.warning("competitive: JSON parse failed twice")
            return {"companies": [], "messages": [ai]}

        return {"companies": parsed, "messages": [ai]}

    return node
