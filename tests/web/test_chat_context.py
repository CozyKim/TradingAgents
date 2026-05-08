"""chat_context 빌더 회귀 테스트."""
from datetime import date

from tradingagents_web.models import Analysis
from tradingagents_web.services.chat_context import build_system_prompt


def _analysis(final_state: dict | None = None, decision="BUY", confidence=0.7) -> Analysis:
    return Analysis(
        run_id="r-x",
        ticker="AAPL",
        analysis_date=date(2026, 5, 8),
        status="completed",
        decision=decision,
        confidence=confidence,
        llm_provider="openai",
        llm_deep_model="gpt-5",
        llm_quick_model="gpt-5-mini",
        debate_rounds=1,
        analysts=["market"],
        final_state=final_state or {},
    )


def test_system_prompt_includes_meta():
    prompt = build_system_prompt(_analysis())
    assert "AAPL" in prompt
    assert "2026-05-08" in prompt
    assert "BUY" in prompt
    assert "gpt-5" in prompt


def test_system_prompt_omits_empty_sections():
    prompt = build_system_prompt(_analysis(final_state={}))
    assert "📈 시장 분석" not in prompt


def test_system_prompt_includes_filled_sections():
    fs = {"market_report": "AAPL은 상승 추세", "fundamentals_report": "PE 28"}
    prompt = build_system_prompt(_analysis(final_state=fs))
    assert "📈 시장 분석" in prompt
    assert "AAPL은 상승 추세" in prompt
    assert "📊 펀더멘털" in prompt
    assert "PE 28" in prompt
