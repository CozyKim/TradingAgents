"""Pure scoring helpers for the hot-sector recommendation.

No I/O. Each helper maps a raw signal to a 0~100 score; ``weighted_hotness``
combines the four normalized scores using :data:`WEIGHTS`.
"""

from __future__ import annotations

# Weights MUST sum to 1.0. Web trend dominates because it is the freshest,
# breadth-first signal; community volume next; sentiment + price momentum
# are confirming signals.
WEIGHTS: dict[str, float] = {
    "web_trend": 0.35,
    "community_volume": 0.25,
    "sentiment": 0.20,
    "momentum": 0.20,
}

# Total StockTwits messages (summed over a theme's tickers) at which the
# community-volume signal saturates to 100.
_VOLUME_SATURATION = 90
# Percent-return -> score sensitivity. avg_return_pct * this, centered at 50.
_MOMENTUM_K = 2.5


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def sentiment_score(bullish: int, bearish: int) -> float:
    """Bullish share as 0~100. Neutral 50 when there is no labeled data."""
    total = bullish + bearish
    if total == 0:
        return 50.0
    return _clamp(bullish / total * 100.0)


def volume_score(total_messages: int) -> float:
    """Community chatter volume as 0~100, saturating at _VOLUME_SATURATION."""
    return _clamp(total_messages / _VOLUME_SATURATION * 100.0)


def momentum_score(avg_return_pct: float) -> float:
    """Price/volume momentum as 0~100, centered at 50 for a flat return."""
    return _clamp(50.0 + avg_return_pct * _MOMENTUM_K)


def weighted_hotness(
    *, web_trend: float, community_volume: float, sentiment: float, momentum: float
) -> float:
    """Weighted sum of the four normalized 0~100 signals."""
    return (
        web_trend * WEIGHTS["web_trend"]
        + community_volume * WEIGHTS["community_volume"]
        + sentiment * WEIGHTS["sentiment"]
        + momentum * WEIGHTS["momentum"]
    )
