"""Macro Overview node — first stage of the sector graph.

Produces a free-text Markdown report covering market size, growth, regulation,
and geopolitical context. May call ``web_search`` up to the per-node budget.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from tradingagents.graph_sector.nodes._tool_loop import invoke_with_tool_loop
from tradingagents.graph_sector.state import SectorState
from tradingagents.graph_sector.tools.web_search import SearchBudget, make_web_search_tool

SYSTEM_PROMPT = """당신은 산업 분석가다. 주어진 산업의 **거시 환경**을 한국어 Markdown 보고서로 작성한다.
다음 항목을 반드시 포함하라:

1. 시장 규모 (USD 기준, 출처 명시)
2. 향후 3년 CAGR 추정
3. 핵심 드라이버 3–5개
4. 정책·규제·지정학 요인

근거가 약한 수치는 반드시 "(추정)" 또는 "(2024년 기준)"처럼 출처·시점을 병기하라.
필요하면 `web_search` 도구를 호출해 근거를 보강하라. 도구가 빈 결과를 돌려주면 기존 지식으로만 마무리하라.
"""


def make_macro_overview_node(llm, budget: SearchBudget | None) -> Callable:
    def node(state: SectorState) -> dict[str, Any]:
        tool = None
        if budget is not None:
            budget.current_node = "macro_overview"
            tool = make_web_search_tool(budget)
            chat = llm.bind_tools([tool])
        else:
            chat = llm

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=(
                f"산업: {state.sector_name}\n"
                f"검색 키워드 후보: {', '.join(state.keywords) or '(없음)'}"
            )),
        ]
        if tool is not None:
            ai, _ = invoke_with_tool_loop(chat, tool, messages)
        else:
            ai = chat.invoke(messages)
        content = ai.content if isinstance(ai.content, str) else str(ai.content)
        return {
            "macro_report": content,
            "messages": [ai],
        }

    return node
