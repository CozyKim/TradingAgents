"""Process-global concurrency cap for heavy analysis graph runs.

Each analysis graph (single-ticker :class:`RealRunner`, sector
:class:`RealSectorRunner`) opens many file descriptors at once: LLM HTTP
sockets, yfinance/finnhub connections, and OHLCV cache files. With no ceiling,
concurrent runs — parallel user runs and sector fan-out, all spawned via
``asyncio.create_task`` — can drive the open-fd count past the per-process
limit (on macOS, ``kern.maxfilesperproc``, typically 61440). The failure then
surfaces as ``[Errno 24] Too many open files`` on whichever call happened to
request an fd at that instant (often an unrelated cache ``read_csv``), which
makes the true cause look like the wrong file.

:func:`analysis_slot` returns a semaphore that bounds how many graphs stream
simultaneously, so peak fd usage stays roughly ``limit × per-graph peak`` and
the cap is hit by *waiting*, not by crashing.

The limit is read from the ``WEB_MAX_CONCURRENT_ANALYSES`` environment
variable (default :data:`DEFAULT_MAX_CONCURRENT`); invalid values fall back to
the default and non-positive values are clamped to 1.
"""

from __future__ import annotations

import asyncio
import logging
import os
import weakref

logger = logging.getLogger(__name__)

#: Default number of analysis graphs allowed to run concurrently. Chosen to be
#: small enough that a handful of multi-agent graphs (each opening tens of
#: sockets/files at peak) stay well under the per-process fd limit, while still
#: letting independent runs make progress in parallel.
DEFAULT_MAX_CONCURRENT = 4

_ENV_VAR = "WEB_MAX_CONCURRENT_ANALYSES"

# Keyed by event loop so the semaphore is bound to the loop that awaits it.
# asyncio primitives bind to the running loop on first use and raise if shared
# across loops; production has a single long-lived uvicorn loop, but tests
# spin up a fresh loop per case. A WeakKeyDictionary lets finished loops (and
# their semaphores) be garbage-collected.
_semaphores: weakref.WeakKeyDictionary[
    asyncio.AbstractEventLoop, asyncio.Semaphore
] = weakref.WeakKeyDictionary()


def _resolve_limit() -> int:
    """Resolve the concurrency limit from the environment.

    Returns:
        The configured limit: :data:`DEFAULT_MAX_CONCURRENT` when the env var
        is unset/blank/non-numeric, the parsed value when >= 1, or 1 when the
        parsed value is non-positive.
    """
    raw = os.getenv(_ENV_VAR)
    if raw is None or not raw.strip():
        return DEFAULT_MAX_CONCURRENT
    try:
        value = int(raw)
    except ValueError:
        logger.warning(
            "invalid %s=%r; falling back to %d",
            _ENV_VAR, raw, DEFAULT_MAX_CONCURRENT,
        )
        return DEFAULT_MAX_CONCURRENT
    if value < 1:
        logger.warning("%s=%d is < 1; clamping to 1", _ENV_VAR, value)
        return 1
    return value


def analysis_slot() -> asyncio.Semaphore:
    """Return the per-event-loop semaphore bounding concurrent analysis graphs.

    All heavy graph runners (single-ticker and sector) must acquire this around
    graph execution so the fd cap is global across the process, not per-call.
    The semaphore is created lazily on first use within a running loop and
    reused for every subsequent call on that loop.

    Returns:
        The shared :class:`asyncio.Semaphore` for the current running loop.

    Raises:
        RuntimeError: If called outside a running event loop.
    """
    loop = asyncio.get_running_loop()
    sem = _semaphores.get(loop)
    if sem is None:
        limit = _resolve_limit()
        sem = asyncio.Semaphore(limit)
        _semaphores[loop] = sem
        logger.info("analysis concurrency capped at %d (%s)", limit, _ENV_VAR)
    return sem


def reset_for_testing() -> None:
    """Drop all cached semaphores so the next :func:`analysis_slot` re-reads env.

    Intended only for tests that need to exercise different limits within one
    process; production never calls this.
    """
    _semaphores.clear()
