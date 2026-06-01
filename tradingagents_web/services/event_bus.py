"""In-memory pub/sub bus for analysis run events.

Each run_id has:
  - a bounded history (ring buffer) so new subscribers replay from the start
  - a set of live asyncio.Queue subscribers receiving fresh events
A None sentinel is enqueued when the run finishes so consumers can stop.
"""
from __future__ import annotations

import asyncio
import copy
from collections import deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Literal

EventType = Literal[
    "agent_message",
    "progress",
    "done",
    "error",
    "cancelled",
    "heartbeat",
    # 채팅 turn 전용
    "token",
    "tool_call",
    "tool_result",
    "close",
]


@dataclass(frozen=True)
class AnalysisEvent:
    """An immutable event emitted during a trading analysis run.

    Attributes:
        type: Category of the event.
        data: Arbitrary payload dict associated with the event.
        seq: Monotonic per-run sequence number assigned by publish().
            Clients may use this as Last-Event-ID for SSE resumption.

    Note:
        ``frozen=True`` makes instances hashable and safe to share across
        multiple asyncio queues without defensive copying.
    """

    type: EventType
    data: dict
    seq: int = field(default=0)


class EventBus:
    """In-memory pub/sub bus scoped to a single process.

    One process, single user — no cross-worker fanout needed. Each run_id
    maintains an independent ring buffer (history) and a live set of
    subscriber queues.

    Args:
        max_buffer: Maximum number of events retained in history per run.
            Older events are dropped when the buffer is full (FIFO eviction).

    Example:
        >>> bus = EventBus()
        >>> bus.publish("run-1", AnalysisEvent(type="progress", data={"step": 1}))
        >>> async with bus.subscribe("run-1") as q:
        ...     ev = await q.get()  # replays history, then live events
    """

    def __init__(self, max_buffer: int = 500) -> None:
        self._max = max_buffer
        self._history: dict[str, deque[AnalysisEvent]] = {}
        self._subs: dict[str, set[asyncio.Queue[AnalysisEvent | None]]] = {}
        self._counters: dict[str, int] = {}
        self._finished: set[str] = set()

    def publish(
        self, run_id: str, event: AnalysisEvent, *, buffer: bool = True
    ) -> AnalysisEvent:
        """Publish an event to all subscribers and (optionally) append to history.

        Assigns a monotonic per-run sequence number before storing/forwarding.
        If the history buffer is full the oldest event is silently dropped.

        Args:
            run_id: Identifier of the analysis run.
            event: The event to publish. The ``seq`` field is overwritten.
            buffer: When False the event is delivered to live subscribers only
                and NOT retained in history. Used for heartbeats so that a
                re-subscribing client never replays stale liveness signals.

        Returns:
            The stamped event with its assigned sequence number.
        """
        seq = self._counters.get(run_id, 0) + 1
        self._counters[run_id] = seq
        stamped = AnalysisEvent(type=event.type, data=copy.copy(event.data), seq=seq)

        if buffer:
            buf = self._history.setdefault(run_id, deque(maxlen=self._max))
            buf.append(stamped)

        for q in list(self._subs.get(run_id, set())):
            q.put_nowait(stamped)
        return stamped

    def finish(self, run_id: str) -> None:
        """Mark a run as finished and push a None sentinel to all subscribers.

        After calling this method, any new subscriber via :meth:`subscribe`
        will also receive the sentinel immediately after history replay.

        Args:
            run_id: Identifier of the analysis run to close.
        """
        self._finished.add(run_id)
        for q in list(self._subs.get(run_id, set())):
            q.put_nowait(None)

    def history(self, run_id: str) -> list[AnalysisEvent]:
        """Return a snapshot of the current history buffer for a run.

        Args:
            run_id: Identifier of the analysis run.

        Returns:
            Ordered list of retained events (oldest first).
        """
        return list(self._history.get(run_id, []))

    def is_finished(self, run_id: str) -> bool:
        """Check whether a run has been marked as finished.

        Args:
            run_id: Identifier of the analysis run.

        Returns:
            True if :meth:`finish` was called for this run_id.
        """
        return run_id in self._finished

    @asynccontextmanager
    async def subscribe(self, run_id: str) -> AsyncIterator[asyncio.Queue[AnalysisEvent | None]]:
        """Async context manager that yields a queue for the given run.

        On entry the current history is replayed into the queue, followed by
        a None sentinel if the run is already finished. While the context is
        active, live events published via :meth:`publish` are also enqueued.
        The subscriber is removed automatically on exit.

        Args:
            run_id: Identifier of the analysis run to subscribe to.

        Yields:
            An ``asyncio.Queue`` that delivers :class:`AnalysisEvent` items
            (or ``None`` as a terminal sentinel).

        Example:
            >>> async with bus.subscribe("run-1") as queue:
            ...     while (ev := await queue.get()) is not None:
            ...         process(ev)
        """
        queue: asyncio.Queue[AnalysisEvent | None] = asyncio.Queue()

        # Replay history so late subscribers catch up
        for ev in self.history(run_id):
            queue.put_nowait(ev)
        # If already finished, push sentinel after replay
        if self.is_finished(run_id):
            queue.put_nowait(None)

        self._subs.setdefault(run_id, set()).add(queue)
        try:
            yield queue
        finally:
            subs = self._subs.get(run_id)
            if subs is not None:
                subs.discard(queue)
                if not subs:
                    self._subs.pop(run_id, None)


# ---------------------------------------------------------------------------
# Module-level singleton — one bus per process
# ---------------------------------------------------------------------------

_BUS: EventBus | None = None


def get_event_bus() -> EventBus:
    """Return the process-wide EventBus singleton, creating it on first call.

    Returns:
        The shared :class:`EventBus` instance.
    """
    global _BUS
    if _BUS is None:
        _BUS = EventBus()
    return _BUS


def reset_event_bus() -> None:
    """Drop the singleton. Intended for use in tests only."""
    global _BUS
    _BUS = None
