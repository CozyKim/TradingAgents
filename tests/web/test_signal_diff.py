"""Tests for the pure signal_diff function."""
from dataclasses import dataclass

from tradingagents_web.services.signal_diff import diff_for_completion


@dataclass
class _Stub:
    """Minimal stand-in for an Analysis row — only the fields diff cares about."""
    id: int
    ticker: str
    decision: str | None
    confidence: float | None
    error: str | None = None
    final_state: dict | None = None


def _cfg(
    signal: bool = True,
    completed: bool = False,
    failed: bool = True,
    threshold: float | None = 0.10,
) -> dict[str, object]:
    return {
        "alert_on_signal_change": signal,
        "alert_on_run_completed": completed,
        "alert_on_run_failed": failed,
        "confidence_change_threshold": threshold,
    }


def test_first_completion_no_prior_no_signal_change():
    curr = _Stub(id=1, ticker="AAPL", decision="BUY", confidence=0.7)
    out = diff_for_completion(curr, prior=None, status="completed", config=_cfg())
    assert all(o.type != "signal_change" for o in out)


def test_first_completion_run_completed_alert_when_enabled():
    curr = _Stub(id=1, ticker="AAPL", decision="BUY", confidence=0.7)
    out = diff_for_completion(
        curr, prior=None, status="completed", config=_cfg(completed=True)
    )
    assert any(o.type == "run_completed" for o in out)


def test_signal_change_emits_signal_change():
    prior = _Stub(id=1, ticker="AAPL", decision="HOLD", confidence=0.6)
    curr = _Stub(
        id=2,
        ticker="AAPL",
        decision="BUY",
        confidence=0.78,
        final_state={"final_trade_decision": "FINAL TRANSACTION PROPOSAL: **BUY**\n…rationale…"},
    )
    out = diff_for_completion(curr, prior=prior, status="completed", config=_cfg())
    types = [o.type for o in out]
    assert "signal_change" in types
    sc = next(o for o in out if o.type == "signal_change")
    assert sc.payload == {
        "prev": "HOLD",
        "curr": "BUY",
        "confidence": 0.78,
        "prev_confidence": 0.6,
        "final_decision_text": "FINAL TRANSACTION PROPOSAL: **BUY**\n…rationale…",
    }


def test_same_decision_no_signal_change():
    prior = _Stub(id=1, ticker="AAPL", decision="BUY", confidence=0.7)
    curr = _Stub(id=2, ticker="AAPL", decision="BUY", confidence=0.72)
    out = diff_for_completion(curr, prior=prior, status="completed", config=_cfg())
    assert all(o.type != "signal_change" for o in out)


def test_confidence_change_above_threshold_emits():
    prior = _Stub(id=1, ticker="AAPL", decision="BUY", confidence=0.5)
    curr = _Stub(id=2, ticker="AAPL", decision="BUY", confidence=0.65)
    out = diff_for_completion(curr, prior=prior, status="completed", config=_cfg())
    assert any(o.type == "confidence_change" for o in out)


def test_confidence_change_below_threshold_skipped():
    prior = _Stub(id=1, ticker="AAPL", decision="BUY", confidence=0.5)
    curr = _Stub(id=2, ticker="AAPL", decision="BUY", confidence=0.55)
    out = diff_for_completion(curr, prior=prior, status="completed", config=_cfg())
    assert all(o.type != "confidence_change" for o in out)


def test_failed_status_emits_run_failed():
    curr = _Stub(id=1, ticker="AAPL", decision=None, confidence=None, error="boom")
    out = diff_for_completion(curr, prior=None, status="failed", config=_cfg())
    assert any(o.type == "run_failed" for o in out)
    rf = next(o for o in out if o.type == "run_failed")
    assert rf.payload["error"] == "boom"


def test_threshold_none_disables_confidence_alert():
    prior = _Stub(id=1, ticker="AAPL", decision="BUY", confidence=0.4)
    curr = _Stub(id=2, ticker="AAPL", decision="BUY", confidence=0.9)
    out = diff_for_completion(
        curr, prior=prior, status="completed", config=_cfg(threshold=None)
    )
    assert all(o.type != "confidence_change" for o in out)


def test_signal_and_confidence_both_emit_in_priority_order():
    """Decision changed AND |Δconfidence| ≥ threshold AND completed alerts on:
    all three outcomes appear, in declared priority order."""
    prior = _Stub(id=1, ticker="AAPL", decision="HOLD", confidence=0.4)
    curr = _Stub(id=2, ticker="AAPL", decision="BUY", confidence=0.9)
    out = diff_for_completion(
        curr, prior=prior, status="completed", config=_cfg(completed=True)
    )
    assert [o.type for o in out] == [
        "signal_change",
        "confidence_change",
        "run_completed",
    ]
