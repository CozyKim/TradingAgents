"""시스템 프롬프트 + 메시지 히스토리 빌더 + 요약 프롬프트."""
from __future__ import annotations

from typing import Any

from langchain.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from sqlalchemy.orm import Session as OrmSession

from tradingagents_web.models import Analysis, ChatMessage

_REPORT_SECTIONS: list[tuple[str, str]] = [
    ("market_report", "📈 시장 분석"),
    ("sentiment_report", "💬 시장 심리"),
    ("news_report", "📰 뉴스"),
    ("fundamentals_report", "📊 펀더멘털"),
    ("investment_plan", "🧠 리서처 결론"),
    ("trader_investment_plan", "💼 트레이더 플랜"),
    ("final_trade_decision", "🎯 최종 결정"),
]


def build_system_prompt(analysis: Analysis) -> str:
    """완료된 분석 결과를 채팅 시스템 프롬프트로 변환.

    Args:
        analysis: 완료된 Analysis 행.

    Returns:
        LangChain agent의 system_prompt에 전달할 한국어 프롬프트 문자열.
    """
    state: dict[str, Any] = analysis.final_state or {}
    body_parts: list[str] = []
    for key, label in _REPORT_SECTIONS:
        text = state.get(key)
        if isinstance(text, str) and text.strip():
            body_parts.append(f"## {label}\n{text.strip()}")
    body = "\n\n".join(body_parts) if body_parts else "(분석 본문 없음)"

    return (
        "당신은 TradingAgents가 수행한 분석 결과를 바탕으로 후속 질문에 답하는 "
        "한국어 어시스턴트입니다.\n\n"
        "## 분석 메타\n"
        f"- 종목: {analysis.ticker}\n"
        f"- 분석일: {analysis.analysis_date}\n"
        f"- 결정: {analysis.decision} (신뢰도 {analysis.confidence})\n"
        f"- 사용 모델: {analysis.llm_provider} / deep={analysis.llm_deep_model}\n\n"
        "## 도구 사용 규칙\n"
        "- 분석 당시 데이터로 답할 수 있으면 도구를 호출하지 말고 본문 컨텍스트로 답하세요.\n"
        '- 사용자가 "지금", "최신", "오늘" 같은 표현으로 새 데이터를 요구하면 도구를 호출하세요.\n'
        f'- 도구 호출 시 ticker 기본은 "{analysis.ticker}", 분석 기준일은 '
        f'"{analysis.analysis_date}"입니다.\n'
        "- 한 번의 응답에서 동일 도구를 같은 인자로 두 번 호출하지 마세요.\n\n"
        "## 응답 스타일\n"
        "- 한국어로 답하세요. 사용자가 영어로 물어도 한국어 우선.\n"
        "- 결정에 대한 근거를 묻는 질문에는 위 컨텍스트의 해당 섹션을 인용해 설명하세요.\n"
        '- 추측이 필요한 경우 "분석 시점 데이터 기준" 같은 단서를 명시하세요.\n\n'
        "## 분석 본문 (참고용 컨텍스트)\n"
        f"{body}\n"
    )



def _to_lc_message(row: ChatMessage) -> AnyMessage:
    """ChatMessage 행을 LangChain 메시지 객체로 변환.

    Args:
        row: ChatMessage 모델 인스턴스.

    Returns:
        역할에 따른 HumanMessage, AIMessage, 또는 ToolMessage.

    Raises:
        ValueError: 알 수 없는 role 값.
    """
    if row.role == "user":
        return HumanMessage(content=row.content_blocks)
    if row.role == "assistant":
        return AIMessage(content=row.content_blocks, tool_calls=row.tool_calls or [])
    if row.role == "tool":
        return ToolMessage(
            content=row.content_blocks,
            tool_call_id=row.tool_call_id or "",
            name=row.tool_name or "",
        )
    raise ValueError(f"unknown role: {row.role}")


def build_message_history(
    db: OrmSession,
    analysis_id: int,
    *,
    window_n: int = 8,
) -> list[AnyMessage]:
    """analysis의 최근 window_n개 turn에 속한 메시지를 LangChain 메시지로 반환.

    Args:
        db: SQLAlchemy 세션.
        analysis_id: 대상 분석의 PK.
        window_n: 유지할 turn 개수(첫 등장 순서 기준 마지막 N개).

    Returns:
        sequence 정순으로 정렬된 LangChain 메시지 객체 리스트.
    """
    rows: list[ChatMessage] = (
        db.query(ChatMessage)
        .filter(ChatMessage.analysis_id == analysis_id)
        .order_by(ChatMessage.sequence.asc())
        .all()
    )
    seen: list[str] = []
    for r in rows:
        if r.turn_id not in seen:
            seen.append(r.turn_id)
    keep_turns = set(seen[-window_n:])
    return [_to_lc_message(r) for r in rows if r.turn_id in keep_turns]
