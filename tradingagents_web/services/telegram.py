"""Minimal async Telegram Bot API client.

Only what the notifier needs: sendMessage (push) and getMe (token validation).
Calls are short-lived AsyncClient sessions; we do not maintain a pool because
notification volume is low (handful per day) and avoids cross-event-loop
client reuse pitfalls in tests.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org"
DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


async def send_message(
    *,
    bot_token: str,
    chat_id: str,
    text: str,
    parse_mode: str | None = "MarkdownV2",
) -> bool:
    """POST sendMessage. Returns True on Telegram ``ok=true``, False otherwise.

    Network failures, non-200 responses, and malformed (non-JSON) bodies are
    all logged and swallowed; alerting must never raise into the analysis
    pipeline.

    Args:
        bot_token: Telegram Bot API token (e.g. ``"123456:ABC-DEF"``).
        chat_id: Target chat or channel ID as a string.
        text: Message body to send. Caller is responsible for escaping
            MarkdownV2 special characters when ``parse_mode="MarkdownV2"``.
        parse_mode: Telegram parse mode. Defaults to ``"MarkdownV2"``.
            Pass ``None`` to send plain text.

    Returns:
        ``True`` if Telegram responded with ``ok=true``, ``False`` on any error.
    """
    url = f"{API_BASE}/bot{bot_token}/sendMessage"
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
        if resp.status_code != 200:
            logger.warning(
                "Telegram sendMessage non-200: %s %s",
                resp.status_code,
                resp.text[:200],
            )
            return False
        body = resp.json()
        return bool(body.get("ok"))
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Telegram sendMessage failed: %s", exc)
        return False


async def get_me(bot_token: str) -> dict[str, Any]:
    """GET getMe — verifies a bot token. Always returns a dict.

    Returns:
        ``{"ok": True, "username": "<botname>"}`` on success.
        ``{"ok": False, "error": "<reason>"}`` on any failure (network,
        non-200, or non-JSON body).

    Args:
        bot_token: Telegram Bot API token to validate.
    """
    url = f"{API_BASE}/bot{bot_token}/getMe"
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            resp = await client.get(url)
        if resp.status_code != 200:
            # Non-200 response: try to extract error from JSON if available,
            # otherwise fall back to HTTP status code.
            try:
                body = resp.json()
                return {
                    "ok": False,
                    "error": body.get("description") or f"HTTP {resp.status_code}",
                }
            except ValueError:
                # Response body is not JSON (e.g., HTML error page).
                return {"ok": False, "error": f"HTTP {resp.status_code}"}
        body = resp.json()
        if not body.get("ok"):
            return {
                "ok": False,
                "error": body.get("description") or f"HTTP {resp.status_code}",
            }
        return {"ok": True, "username": body.get("result", {}).get("username")}
    except (httpx.HTTPError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}
