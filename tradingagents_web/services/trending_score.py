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
# Saturation point: ±20% avg return maps to ~100 / ~0  (50 / 2.5 = 20).
_MOMENTUM_K = 2.5


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def sentiment_score(bullish: int, bearish: int) -> float:
    """Bullish share as 0~100. Neutral 50 when there is no labeled data.

    Args:
        bullish: Number of bullish messages or votes for the theme.
        bearish: Number of bearish messages or votes for the theme.

    Returns:
        A float in [0, 100] representing the bullish percentage. Returns 50.0
        when both counts are zero (no sentiment data available).
    """
    total = bullish + bearish
    if total == 0:
        return 50.0
    return _clamp(bullish / total * 100.0)


def volume_score(total_messages: int) -> float:
    """Community chatter volume as 0~100, saturating at _VOLUME_SATURATION.

    Args:
        total_messages: Total StockTwits (or equivalent) messages summed over
            all tickers belonging to a theme.

    Returns:
        A float in [0, 100]. Returns 0.0 when ``_VOLUME_SATURATION <= 0``
        (misconfiguration guard) or when ``total_messages`` is 0.
    """
    if _VOLUME_SATURATION <= 0:
        return 0.0
    return _clamp(total_messages / _VOLUME_SATURATION * 100.0)


def momentum_score(avg_return_pct: float) -> float:
    """Price/volume momentum as 0~100, centered at 50 for a flat return.

    Args:
        avg_return_pct: Average percentage return of the theme's tickers over
            the lookback window (e.g. ``5.0`` for a +5% average move).

    Returns:
        A float in [0, 100]. A return of 0% yields 50. The score saturates at
        100 for returns >= +20% and at 0 for returns <= -20%.
    """
    return _clamp(50.0 + avg_return_pct * _MOMENTUM_K)


def weighted_hotness(
    *, web_trend: float, community_volume: float, sentiment: float, momentum: float
) -> float:
    """Weighted sum of the four normalized 0~100 signals.

    Each input is expected to already be in [0, 100] — i.e. the output of
    :func:`sentiment_score`, :func:`volume_score`, :func:`momentum_score`, or
    a Google Trends / similar rescaled web-trend value.

    Args:
        web_trend: Web search / Google Trends score in [0, 100].
        community_volume: Community message-volume score in [0, 100] from
            :func:`volume_score`.
        sentiment: Bullish-sentiment score in [0, 100] from
            :func:`sentiment_score`.
        momentum: Price-momentum score in [0, 100] from
            :func:`momentum_score`.

    Returns:
        A float in [0, 100] representing the composite hotness score.
        Returns 100 when all four inputs are 100, and 0 when all are 0.
    """
    return (
        web_trend * WEIGHTS["web_trend"]
        + community_volume * WEIGHTS["community_volume"]
        + sentiment * WEIGHTS["sentiment"]
        + momentum * WEIGHTS["momentum"]
    )
