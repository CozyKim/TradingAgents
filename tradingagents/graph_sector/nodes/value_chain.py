"""Value-Chain node — second stage. Forces JSON output with mermaid string."""
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


SYSTEM_PROMPT = """당신은 산업 분석가다. 주어진 산업의 **가치사슬(Value Chain)**을 분해한다.

반드시 다음 형식의 JSON만 출력하라(마크다운 코드블록 없이 순수 JSON):

{
  "stages": [
    {"name": "Upstream — 소재/장비", "description": "...", "key_companies": ["..."]},
    {"name": "Midstream — 제조", "description": "...", "key_companies": ["..."]},
    {"name": "Downstream — 최종 제품/서비스", "description": "...", "key_companies": ["..."]}
  ],
  "mermaid": "graph LR\\n  U[Upstream] --> M[Midstream] --> D[Downstream]"
}

stages는 3–6개. mermaid 구문은 `graph LR` 또는 `flowchart LR`로 시작해야 한다.
필요하면 `web_search`로 보강하라."""


def _try_parse(content: str) -> dict | None:
    """Parse JSON from raw text, tolerating ```json fences."""
    s = content.strip()
    if s.startswith("```"):
        # strip first fence line + trailing ```
        s = "\n".join(line for line in s.splitlines() if not line.startswith("```"))
    try:
        data = json.loads(s)
    except json.JSONDecodeError:
        return None
    # Shape validation: parsing alone isn't enough. _render_md() iterates
    # stages and joins key_companies — if any of those have the wrong type
    # the node would crash with TypeError downstream and skip the retry path.
    if not isinstance(data, dict):
        return None
    if not isinstance(data.get("mermaid"), str):
        return None
    stages = data.get("stages")
    if not isinstance(stages, list):
        return None
    for stage in stages:
        if not isinstance(stage, dict):
            return None
        companies = stage.get("key_companies")
        if companies is not None and not (
            isinstance(companies, list)
            and all(isinstance(c, str) for c in companies)
        ):
            return None
    return data


def _render_md(stages: list[dict]) -> str:
    lines = ["## 가치사슬 단계별 분해"]
    for stage in stages:
        lines.append(f"\n### {stage.get('name', '?')}")
        if desc := stage.get("description"):
            lines.append(desc)
        if companies := stage.get("key_companies"):
            lines.append("\n**주요 기업:** " + ", ".join(companies))
    return "\n".join(lines)


def _invoke(chat, tool, messages):
    """Call the model with tool-loop when a tool is bound, else plain invoke."""
    if tool is not None:
        ai, history = invoke_with_tool_loop(chat, tool, messages)
        return ai, history
    ai = chat.invoke(messages)
    return ai, list(messages) + [ai]


def make_value_chain_node(llm, budget: SearchBudget | None) -> Callable:
    """Build the value_chain node.

    NOTE on budget lifetime: same closure-capture rule as
    ``make_macro_overview_node``. The graph must be rebuilt per analysis
    run with a fresh ``SearchBudget``; otherwise web_search call counts
    leak across runs.
    """
    def node(state: SectorState) -> dict[str, Any]:
        tool = None
        if budget is not None:
            budget.current_node = "value_chain"
            tool = make_web_search_tool(budget)
            chat = llm.bind_tools([tool])
        else:
            chat = llm

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=(
                f"산업: {state.sector_name}\n"
                f"키워드: {', '.join(state.keywords)}\n\n"
                f"거시 컨텍스트:\n{state.macro_report[:2000]}"
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
            logger.warning("value_chain: JSON parse failed twice; falling back to raw text")
            return {
                "value_chain_md": raw,
                "value_chain_mermaid": "",
                "messages": [ai],
            }

        return {
            "value_chain_md": _render_md(parsed["stages"]),
            "value_chain_mermaid": parsed["mermaid"],
            "messages": [ai],
        }

    return node
