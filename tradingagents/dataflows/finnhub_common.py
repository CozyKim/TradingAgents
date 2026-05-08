"""Shared Finnhub HTTP plumbing: auth, error classes, request helper."""

from __future__ import annotations

import os
import logging
from typing import Any

import requests

API_BASE_URL = "https://finnhub.io/api/v1"
_TIMEOUT_SECONDS = 10
_log = logging.getLogger(__name__)


class FinnhubAuthError(RuntimeError):
    """Raised when Finnhub returns 401/403 (bad/missing key)."""


class FinnhubRateLimitError(RuntimeError):
    """Raised when Finnhub returns 429 (rate limit exceeded)."""


def get_api_key() -> str | None:
    """Return FINNHUB_API_KEY env var or None when unset."""
    key = os.getenv("FINNHUB_API_KEY")
    return key.strip() if key and key.strip() else None


def finnhub_get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    """GET helper that adds the API key and maps HTTP errors to typed exceptions.

    Args:
        path: Path under the API base, e.g. "/stock/social-sentiment".
        params: Query parameters (must NOT include "token").

    Returns:
        The parsed JSON body (always a dict; list payloads are wrapped under "items").

    Raises:
        FinnhubAuthError: 401/403 response.
        FinnhubRateLimitError: 429 response.
        requests.RequestException: network-level failure (caller decides how to surface).
    """
    key = get_api_key()
    if not key:
        raise FinnhubAuthError("FINNHUB_API_KEY not set")

    query = dict(params)
    query["token"] = key
    url = f"{API_BASE_URL}{path}"
    _log.debug("finnhub_get path=%s params=%s", path, {k: v for k, v in params.items()})
    resp = requests.get(url, params=query, timeout=_TIMEOUT_SECONDS)

    if resp.status_code in (401, 403):
        raise FinnhubAuthError(f"Finnhub auth failed (HTTP {resp.status_code}).")
    if resp.status_code == 429:
        raise FinnhubRateLimitError("Finnhub rate limit exceeded (HTTP 429).")
    resp.raise_for_status()

    body = resp.json()
    if isinstance(body, list):
        return {"items": body}
    return body
