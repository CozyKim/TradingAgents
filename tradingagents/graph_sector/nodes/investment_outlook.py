"""Investment Outlook node — final stage.

Synthesizes prior stage outputs into an investment outlook + candidate ticker
list. No web_search at this stage — purely synthesis.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from tradingagents.graph_sector.state import SectorState

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """당신은 산업 분석가다. 주어진 컨텍스트를 종합해 **투자 전망**과 **후보 종목**을 정리한다.

다음 JSON만 출력하라(코드블록 없이):

{
  "summary_md": "## 수혜\\n...\\n## 리스크\\n...",
  "candidate_tickers": [
    {"ticker": "AAPL", "name": "Apple", "stage": "Downstream — 디바이스", "reason": "..."}
  ]
}

candidate_tickers는 5–10개. 한국·미국·기타 시장을 균형 있게 포함하라.
reason은 가치사슬 어느 단계에서 어떤 이유로 수혜인지 한 문장."""


def _try_parse(content: str) -> dict | None:
    """Parse JSON from raw text, tolerating ```json fences and validating shape."""
    s = content.strip()
    if s.startswith("```"):
        s = "\n".join(line for line in s.splitlines() if not line.startswith("```"))
    try:
        data = json.loads(s)
    except json.JSONDecodeError:
        return None
    # Shape validation: parse success isn't enough — downstream code expects
    # summary_md as str and candidate_tickers as a list of dicts.
    if not isinstance(data, dict):
        return None
    if not isinstance(data.get("summary_md"), str):
        return None
    candidates = data.get("candidate_tickers", [])
    if not isinstance(candidates, list):
        return None
    if not all(isinstance(c, dict) for c in candidates):
        return None
    return data


def make_investment_outlook_node(llm) -> Callable:
    """Build the investment_outlook node.

    No web_search — this stage is pure synthesis from earlier state. No
    closure-captured budget either; safe to reuse across runs.
    """
    def node(state: SectorState) -> dict[str, Any]:
        companies_brief = "\n".join(
            f"- {c['name']} ({c.get('ticker', '?')}): {c['stage']} {c['share_value']}% ({c['share_basis']})"
            for c in state.companies[:20]
        )
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=(
                f"산업: {state.sector_name}\n\n"
                f"거시:\n{state.macro_report[:1500]}\n\n"
                f"가치사슬:\n{state.value_chain_md[:1500]}\n\n"
                f"경쟁사:\n{companies_brief}"
            )),
        ]
        ai = llm.invoke(messages)
        raw = ai.content if isinstance(ai.content, str) else str(ai.content)
        parsed = _try_parse(raw)
        if parsed is None:
            retry_msgs = [*messages, ai, HumanMessage(content="JSON만 다시 출력하라.")]
            ai = llm.invoke(retry_msgs)
            raw = ai.content if isinstance(ai.content, str) else str(ai.content)
            parsed = _try_parse(raw)

        if parsed is None:
            logger.warning("outlook: JSON parse failed twice")
            return {
                "outlook_md": raw,
                "candidate_tickers": [],
                "messages": [ai],
            }

        candidates = [
            {
                "ticker": str(c.get("ticker", "")),
                "name": str(c.get("name", "")),
                "stage": str(c.get("stage", "")),
                "reason": str(c.get("reason", "")),
            }
            for c in parsed.get("candidate_tickers", [])
            if c.get("ticker")
        ]
        return {
            "outlook_md": parsed.get("summary_md", ""),
            "candidate_tickers": candidates,
            "messages": [ai],
        }

    return node
