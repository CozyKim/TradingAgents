"""Shared yfinance session/locking regression tests.

Guards the fd-leak fix (2026-06-11): the curl_cffi default of one Curl
handle per thread leaks sockets/pipes in persistent thread pools, so all
yfinance traffic must go through a single shared handle serialized by
YF_LOCK.
"""

import threading

import pandas as pd
import pytest

from tradingagents.dataflows import stockstats_utils
from tradingagents.dataflows._yf_lock import YF_LOCK, ensure_shared_yf_session
from tradingagents.dataflows.stockstats_utils import yf_retry


def test_ensure_shared_yf_session_disables_thread_local_curl():
    """The injected session must share one Curl handle across threads."""
    from yfinance.data import YfData

    ensure_shared_yf_session()
    session = YfData()._session

    assert session._use_thread_local_curl is False


def test_ensure_shared_yf_session_is_idempotent():
    from yfinance.data import YfData

    ensure_shared_yf_session()
    first = YfData()._session
    ensure_shared_yf_session()

    assert YfData()._session is first


def test_yf_retry_holds_lock_during_call():
    seen: dict[str, bool] = {}

    def probe():
        seen["locked"] = YF_LOCK.locked()
        return "ok"

    assert yf_retry(probe) == "ok"
    assert seen["locked"] is True
    assert YF_LOCK.locked() is False


def test_yf_retry_sleeps_outside_lock_on_rate_limit(monkeypatch):
    from yfinance.exceptions import YFRateLimitError

    calls = {"n": 0}
    sleep_lock_state: list[bool] = []

    def flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise YFRateLimitError()
        return "recovered"

    monkeypatch.setattr(
        stockstats_utils.time,
        "sleep",
        lambda _s: sleep_lock_state.append(YF_LOCK.locked()),
    )

    assert yf_retry(flaky) == "recovered"
    assert calls["n"] == 2
    assert sleep_lock_state == [False]


def test_load_ohlcv_does_not_deadlock(monkeypatch, tmp_path):
    """load_ohlcv must not wrap yf_retry in YF_LOCK again (non-reentrant)."""
    frame = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-06-08", "2026-06-09"]),
            "Open": [1.0, 2.0],
            "High": [1.0, 2.0],
            "Low": [1.0, 2.0],
            "Close": [1.0, 2.0],
            "Volume": [100, 200],
        }
    ).set_index("Date")

    monkeypatch.setattr(
        stockstats_utils,
        "get_config",
        lambda: {"data_cache_dir": str(tmp_path)},
    )
    monkeypatch.setattr(
        stockstats_utils.yf, "download", lambda *a, **k: frame
    )

    result: dict[str, pd.DataFrame] = {}

    def run():
        result["df"] = stockstats_utils.load_ohlcv("FAKE", "2026-06-09")

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(timeout=10)

    if t.is_alive():
        pytest.fail("load_ohlcv deadlocked on YF_LOCK")
    assert not result["df"].empty
