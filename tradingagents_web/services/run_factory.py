"""Pick the runner implementation based on settings."""
from __future__ import annotations

from tradingagents_web.config import Settings
from tradingagents_web.services.event_bus import get_event_bus
from tradingagents_web.services.runner import FakeRunner, RealRunner, Runner


def make_runner(settings: Settings | None = None) -> Runner:
    """Return the appropriate Runner implementation based on settings.

    When ``settings.fake_runner`` is True, returns a :class:`FakeRunner`
    that emits a deterministic event sequence without any LLM calls.
    Otherwise returns a :class:`RealRunner` that streams the actual
    TradingAgentsGraph.

    Args:
        settings: Application settings. If None, a fresh Settings() instance
            is constructed (reads from environment / .env file).

    Returns:
        A :class:`Runner`-protocol-compatible object ready to call ``.run()``.

    Example:
        >>> runner = make_runner()
        >>> result = await runner.run(request)
    """
    settings = settings or Settings()
    bus = get_event_bus()
    if settings.fake_runner:
        return FakeRunner(bus=bus, delay=settings.fake_runner_delay_seconds)
    return RealRunner(bus=bus)
