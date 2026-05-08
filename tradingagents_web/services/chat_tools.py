"""채팅 어시스턴트가 호출할 수 있는 도구 묶음."""
from __future__ import annotations

from typing import Any

from tradingagents.agents.utils.agent_utils import (
    get_balance_sheet,
    get_cashflow,
    get_fundamentals,
    get_global_news,
    get_income_statement,
    get_indicators,
    get_insider_transactions,
    get_news,
    get_stock_data,
)

CHAT_TOOLS: list[Any] = [
    get_stock_data,
    get_indicators,
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
    get_news,
    get_insider_transactions,
    get_global_news,
]


def get_chat_tools(analysis: Any) -> list[Any]:
    """채팅 어시스턴트에게 노출할 도구 목록.

    현재는 분석에 무관하게 9개를 그대로 반환한다. analysis 파라미터는
    추후 분석가 종류별 도구 게이팅(예: news 분석가가 아닌 분석에서 뉴스
    도구 비활성화) 확장을 위한 hook이다.

    Args:
        analysis: 대상 Analysis 행 또는 None.

    Returns:
        LangChain Tool 객체 9개의 리스트.
    """
    return CHAT_TOOLS
