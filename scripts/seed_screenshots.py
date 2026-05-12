"""Seed the E2E sqlite sandbox with deterministic demo data for README screenshots.

This script is the *only* sanctioned way to populate the screenshot fixture
database. It refuses to run against the production DB and only writes to the
relative-path sqlite file declared in ``.env.test`` (``./tradingagents_web_e2e.db``).

Usage:
    set -a && source .env.test && set +a
    uv run python scripts/seed_screenshots.py

The data is intentionally rounded (avg_cost = $150, $400, $250) so it reads
clearly as demo data and never leaks real purchase prices.
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure project root is on sys.path so we can import tradingagents_web.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from tradingagents_web.models.alert import Alert
from tradingagents_web.models.analysis import Analysis
from tradingagents_web.models.holding import Holding
from tradingagents_web.models.schedule import Schedule


def _guard_against_prod_db(database_url: str) -> None:
    """Refuse to write to the production sqlite file."""
    home_db = str(Path.home() / ".tradingagents" / "web.db")
    if home_db in database_url:
        raise SystemExit(
            f"[seed_screenshots] REFUSING — WEB_DATABASE_URL points at production DB:\n"
            f"   {database_url}\n"
            f"   Expected a relative path inside the working tree (use .env.test)."
        )


def _utc(days_ago: float = 0.0, hours_ago: float = 0.0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days_ago, hours=hours_ago)


def _make_final_state(
    ticker: str,
    decision: str,
    bullish: bool,
) -> dict[str, str]:
    """Build a realistic-looking final_state for the detail page."""
    tone = "강한 상승 모멘텀" if bullish else "단기 조정 가능성"
    return {
        "market_report": (
            f"## {ticker} 시장 분석\n\n"
            f"최근 30일간 {ticker}는 {tone}을 보이고 있다. "
            f"이동평균선 정렬과 거래량 패턴은 추세 추종 시그널과 정합한다.\n\n"
            f"- **MACD**: 양수 영역, 시그널선 상회\n"
            f"- **RSI(14)**: 58 (과매수/과매도 중립)\n"
            f"- **거래량**: 20일 평균 대비 +12%"
        ),
        "sentiment_report": (
            f"## 소셜 센티먼트\n\n"
            f"Reddit r/wallstreetbets, Stocktwits에서 {ticker} 언급량이 지난주 대비 "
            f"{'34% 증가' if bullish else '11% 감소'}. 전반적 톤은 "
            f"{'긍정 67% / 부정 18%' if bullish else '긍정 41% / 부정 38%'}."
        ),
        "news_report": (
            f"## 뉴스 & 매크로\n\n"
            f"이번 주 {ticker} 관련 주요 뉴스:\n"
            f"1. 신제품 발표가 시장 기대치를 상회\n"
            f"2. 동종업계 가이던스 상향\n"
            f"3. Fed 점도표 관련 불확실성은 섹터 전반에 영향"
        ),
        "fundamentals_report": (
            f"## 펀더멘털\n\n"
            f"- P/E: {28.4 if bullish else 34.1}\n"
            f"- 매출 YoY: {'+18%' if bullish else '+6%'}\n"
            f"- FCF 마진: {'24%' if bullish else '17%'}\n"
            f"- 부채/자기자본: 0.32"
        ),
        "investment_plan": (
            f"### Bull vs Bear 토론 결론\n\n"
            f"{'Bull 케이스가 우세' if bullish else 'Bear 케이스가 우세'}하다. "
            f"단기 기술적 지표와 펀더멘털이 모두 같은 방향을 가리킨다."
        ),
        "trader_investment_plan": (
            f"포지션: {decision}\n"
            f"진입 구간: 현재가 대비 ±2% 윈도우\n"
            f"손절: -7%, 익절 1차: +12% / 2차: +20%\n"
            f"홀딩 기간: 4–8주"
        ),
        "final_trade_decision": decision,
    }


def seed(database_url: str) -> None:
    _guard_against_prod_db(database_url)
    engine = create_engine(database_url, future=True)

    with Session(engine) as session:
        # 1) Reset demo tables (idempotent re-seed). Users/sessions stay as-is.
        session.execute(delete(Alert))
        session.execute(delete(Analysis))
        session.execute(delete(Schedule))
        session.execute(delete(Holding))

        # 2) Holdings — rounded avg costs so it clearly reads as demo data.
        holdings = [
            Holding(ticker="AAPL",  qty=10.0, avg_cost=150.00, monitor_enabled=True,
                    notes="장기 보유 — 핵심 비중"),
            Holding(ticker="NVDA",  qty=5.0,  avg_cost=400.00, monitor_enabled=True,
                    notes="AI 인프라 테마"),
            Holding(ticker="TSLA",  qty=8.0,  avg_cost=250.00, monitor_enabled=False,
                    notes="변동성 큼, 비중 축소 검토"),
            Holding(ticker="GOOGL", qty=12.0, avg_cost=130.00, monitor_enabled=True),
            Holding(ticker="MSFT",  qty=6.0,  avg_cost=350.00, monitor_enabled=False),
        ]
        session.add_all(holdings)
        session.flush()

        # 3) Analyses — mix of decisions/confidences across the watchlist.
        runs = [
            # (ticker, decision, confidence, days_ago, bullish, status)
            ("AAPL",  "BUY",  0.82, 0.05, True,  "completed"),
            ("AAPL",  "HOLD", 0.61, 1.2,  True,  "completed"),
            ("NVDA",  "BUY",  0.88, 0.10, True,  "completed"),
            ("NVDA",  "BUY",  0.74, 2.0,  True,  "completed"),
            ("TSLA",  "SELL", 0.69, 0.30, False, "completed"),
            ("TSLA",  "HOLD", 0.55, 3.0,  False, "completed"),
            ("GOOGL", "BUY",  0.71, 0.50, True,  "completed"),
            ("MSFT",  "HOLD", 0.58, 1.5,  True,  "completed"),
            # An in-flight run so the dashboard shows a "Running" row.
            ("NVDA",  None,   None, 0.0,  True,  "running"),
        ]

        for ticker, decision, confidence, days_ago, bullish, status in runs:
            created = _utc(days_ago=days_ago)
            completed = None if status == "running" else created + timedelta(minutes=3)
            session.add(
                Analysis(
                    run_id=str(uuid.uuid4()),
                    ticker=ticker,
                    analysis_date=created.date(),
                    status=status,
                    decision=decision,
                    confidence=confidence,
                    llm_provider="openai",
                    llm_deep_model="gpt-5.4",
                    llm_quick_model="gpt-5.4-mini",
                    debate_rounds=2,
                    analysts=["market", "sentiment", "news", "fundamentals"],
                    final_state=(
                        None
                        if status == "running"
                        else _make_final_state(ticker, decision or "HOLD", bullish)
                    ),
                    cost_usd=None if status == "running" else 0.42,
                    created_at=created,
                    completed_at=completed,
                )
            )

        # 4) Schedules — one auto-managed (holding) + one user-defined.
        session.add_all([
            Schedule(
                name="AAPL · 평일 마감 30분 후",
                ticker="AAPL",
                cron_expr="30 21 * * 1-5",
                timezone="UTC",
                preset={
                    "llm_provider": "openai",
                    "llm_deep_model": "gpt-5.4",
                    "llm_quick_model": "gpt-5.4-mini",
                    "analysts": ["market", "sentiment", "news", "fundamentals"],
                    "debate_rounds": 2,
                },
                active=True,
                source="holding",
                last_run=_utc(hours_ago=14),
                next_run=_utc(days_ago=-1),
            ),
            Schedule(
                name="NVDA · 주간 리뷰",
                ticker="NVDA",
                cron_expr="0 22 * * 5",
                timezone="UTC",
                preset={
                    "llm_provider": "openai",
                    "llm_deep_model": "gpt-5.4",
                    "llm_quick_model": "gpt-5.4-mini",
                    "analysts": ["market", "news", "fundamentals"],
                    "debate_rounds": 3,
                },
                active=True,
                source="user",
                last_run=_utc(days_ago=2),
                next_run=_utc(days_ago=-5),
            ),
        ])

        # 5) Alerts — payload keys match what the UI renderer expects
        # (see web/components/alerts/alert-row.tsx::renderSummary).
        session.add_all([
            Alert(
                type="signal_change",
                ticker="TSLA",
                payload={
                    "prev": "HOLD",
                    "curr": "SELL",
                    "confidence": 0.69,
                    "prev_confidence": 0.55,
                },
                read=False,
                created_at=_utc(hours_ago=2),
            ),
            Alert(
                type="confidence_change",
                ticker="NVDA",
                payload={
                    "prev": 0.74,
                    "curr": 0.88,
                    "delta": 0.14,
                },
                read=False,
                created_at=_utc(hours_ago=6),
            ),
            Alert(
                type="run_completed",
                ticker="AAPL",
                payload={"decision": "BUY", "confidence": 0.82},
                read=True,
                created_at=_utc(hours_ago=12),
            ),
            Alert(
                type="schedule_failed",
                ticker="GOOGL",
                payload={
                    "schedule_name": "GOOGL · 평일 마감 30분 후",
                    "error": "Rate limit exceeded — backing off",
                },
                read=False,
                created_at=_utc(days_ago=1),
            ),
        ])

        session.commit()

    print(f"[seed_screenshots] OK — seeded {database_url}")


def main() -> None:
    database_url = os.environ.get("WEB_DATABASE_URL", "")
    if not database_url:
        raise SystemExit(
            "[seed_screenshots] WEB_DATABASE_URL not set — "
            "run `set -a && source .env.test && set +a` first."
        )
    seed(database_url)


if __name__ == "__main__":
    main()
