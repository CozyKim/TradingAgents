"""Process-global lock for yfinance calls.

yfinance is not thread-safe: every call mutates ``yfinance.shared._DFS`` at
module level and builds the returned DataFrame from that shared state. When two
calls overlap, one (or both) frames end up containing the other ticker's
columns — silently corrupting downstream consumers.

Both the web price/fx services and the analysis dataflows fetch from yfinance
in the same process, so the lock must be importable from either side without
creating a circular dependency. Living under ``tradingagents/dataflows`` is
the lowest-shared layer.
"""
from __future__ import annotations

import threading

YF_LOCK: threading.Lock = threading.Lock()

_session_configured = False
_session_init_lock = threading.Lock()


def ensure_shared_yf_session() -> None:
    """Inject a single-Curl-handle session into the yfinance singleton, once.

    curl_cffi's default ``use_thread_local_curl=True`` creates one libcurl
    handle per calling thread. The web backend calls yfinance from
    ``asyncio.to_thread``'s persistent executor threads, so those handles
    (and their connection caches: CLOSE_WAIT sockets, wakeup pipes, tz-cache
    sqlite handles) were never released — on macOS this exhausted the default
    256-fd soft limit and surfaced as proxy ECONNRESET (2026-06-11).

    A single shared handle is NOT safe under concurrent use, which is why
    every yfinance call must also be serialized by ``YF_LOCK`` — already
    required because yfinance mutates module-level shared state.

    Lazy (not import-time) so importing this module stays cheap for web
    tests that never touch yfinance.
    """
    global _session_configured
    if _session_configured:
        return
    with _session_init_lock:
        if _session_configured:
            return
        from curl_cffi import requests as curl_requests
        from yfinance.data import YfData

        YfData(
            session=curl_requests.Session(
                impersonate="chrome", use_thread_local_curl=False
            )
        )
        _session_configured = True
