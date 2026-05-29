"""Unit tests for trending signal normalization + weighted hotness."""

import pytest

from tradingagents_web.services.trending_score import (
    WEIGHTS,
    momentum_score,
    sentiment_score,
    volume_score,
    weighted_hotness,
)


def test_sentiment_score_all_bullish_is_100():
    assert sentiment_score(bullish=10, bearish=0) == 100.0


def test_sentiment_score_no_data_is_neutral_50():
    assert sentiment_score(bullish=0, bearish=0) == 50.0


def test_sentiment_score_half_half_is_50():
    assert sentiment_score(bullish=5, bearish=5) == 50.0


def test_volume_score_caps_at_100():
    # 90 messages is the saturation target -> >=90 maps to 100
    assert volume_score(total_messages=200) == 100.0
    assert volume_score(total_messages=0) == 0.0


def test_momentum_score_clamps_and_centers_at_50():
    # 0% return -> neutral 50
    assert momentum_score(avg_return_pct=0.0) == 50.0
    # large positive return clamps to 100
    assert momentum_score(avg_return_pct=100.0) == 100.0
    # large negative clamps to 0
    assert momentum_score(avg_return_pct=-100.0) == 0.0


def test_weighted_hotness_uses_weights_summing_to_one():
    assert pytest.approx(sum(WEIGHTS.values()), abs=1e-9) == 1.0
    # all signals 100 -> hotness 100
    assert weighted_hotness(
        web_trend=100, community_volume=100, sentiment=100, momentum=100
    ) == pytest.approx(100.0)
