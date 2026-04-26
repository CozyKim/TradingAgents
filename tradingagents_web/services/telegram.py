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
    parse_mode: str | None = "Markdown",
) -> bool:
    """POST sendMessage. Returns True on Telegram ``ok=true``, False otherwise.

    Network failures and non-200 responses are logged and swallowed; alerting
    must never raise into the analysis pipeline.

    Args:
        bot_token: Telegram Bot API token (e.g. ``"123456:ABC-DEF"``).
        chat_id: Target chat or channel ID as a string.
        text: Message body to send.
        parse_mode: Telegram parse mode. Defaults to ``"Markdown"``.
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
    except httpx.HTTPError as exc:
        logger.warning("Telegram sendMessage failed: %s", exc)
        return False


async def get_me(bot_token: str) -> dict[str, Any]:
    """GET getMe — verifies a bot token. Always returns a dict.

    Args:
        bot_token: Telegram Bot API token to validate.

    Returns:
        ``{"ok": True, "username": "<botname>"}`` on success.
        ``{"ok": False, "error": "<reason>"}`` on failure (including network errors).
    """
    url = f"{API_BASE}/bot{bot_token}/getMe"
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            resp = await client.get(url)
        body = resp.json()
        if resp.status_code != 200 or not body.get("ok"):
            return {
                "ok": False,
                "error": body.get("description") or f"HTTP {resp.status_code}",
            }
        return {"ok": True, "username": body.get("result", {}).get("username")}
    except httpx.HTTPError as exc:
        return {"ok": False, "error": str(exc)}
