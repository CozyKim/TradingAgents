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
