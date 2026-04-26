"""Pure decision-diffing logic for the alerting pipeline.

This module is intentionally side-effect free: it inspects two analysis rows
(or one + None) plus a small config dict and returns a list of trigger
outcomes. The notifier is responsible for persisting Alert rows and pushing
to Telegram.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol


class _AnalysisLike(Protocol):
    id: int
    ticker: str
    decision: str | None
    confidence: float | None
    error: str | None


@dataclass(frozen=True)
class DiffOutcome:
    """One trigger result — maps 1:1 to an Alert row about to be created."""

    type: str  # signal_change | confidence_change | run_completed | run_failed
    payload: dict[str, Any]


def diff_for_completion(
    current: _AnalysisLike,
    prior: _AnalysisLike | None,
    *,
    status: str,
    config: Mapping[str, Any],
) -> list[DiffOutcome]:
    """Compute alert outcomes for one analysis transitioning to a terminal state.

    Args:
        current: The analysis that just transitioned to terminal status.
        prior: The most recent ``completed`` analysis for the same ticker
            (excluding ``current``), or None if this is the first.
        status: Terminal status of ``current`` — ``"completed"`` or ``"failed"``.
        config: Mapping with keys ``alert_on_signal_change``,
            ``alert_on_run_completed``, ``alert_on_run_failed``,
            ``confidence_change_threshold`` (None disables that check).

    Returns:
        Outcomes in priority order: signal_change first, then confidence_change,
        then run_completed (if enabled) or run_failed.
    """
    outcomes: list[DiffOutcome] = []

    if status == "failed":
        if config.get("alert_on_run_failed", True):
            outcomes.append(
                DiffOutcome(
                    type="run_failed",
                    payload={
                        "ticker": current.ticker,
                        "error": current.error or "unknown",
                    },
                )
            )
        return outcomes

    # status == "completed"
    if (
        prior is not None
        and current.decision
        and prior.decision
        and current.decision != prior.decision
    ):
        if config.get("alert_on_signal_change", True):
            outcomes.append(
                DiffOutcome(
                    type="signal_change",
                    payload={
                        "prev": prior.decision,
                        "curr": current.decision,
                        "confidence": current.confidence,
                        "prev_confidence": prior.confidence,
                    },
                )
            )

    threshold = config.get("confidence_change_threshold")
    if (
        threshold is not None
        and prior is not None
        and current.confidence is not None
        and prior.confidence is not None
    ):
        delta = abs(current.confidence - prior.confidence)
        if delta >= threshold:
            outcomes.append(
                DiffOutcome(
                    type="confidence_change",
                    payload={
                        "prev": prior.confidence,
                        "curr": current.confidence,
                        "delta": current.confidence - prior.confidence,
                    },
                )
            )

    if config.get("alert_on_run_completed", False):
        outcomes.append(
            DiffOutcome(
                type="run_completed",
                payload={
                    "ticker": current.ticker,
                    "decision": current.decision,
                    "confidence": current.confidence,
                },
            )
        )

    return outcomes
