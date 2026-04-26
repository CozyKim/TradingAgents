"""Tests for the Telegram bot HTTP client."""
import httpx
import pytest
import respx

from tradingagents_web.services import telegram


@pytest.mark.asyncio
async def test_send_message_success():
    with respx.mock(assert_all_called=True) as mock:
        route = mock.post("https://api.telegram.org/botABC:DEF/sendMessage").mock(
            return_value=httpx.Response(
                200, json={"ok": True, "result": {"message_id": 1}}
            )
        )
        ok = await telegram.send_message(
            bot_token="ABC:DEF", chat_id="123", text="hello"
        )
        assert ok is True
        assert route.called
        sent = route.calls.last.request
        assert b'"chat_id":"123"' in sent.content or b"chat_id=123" in sent.content


@pytest.mark.asyncio
async def test_send_message_returns_false_on_4xx():
    with respx.mock() as mock:
        mock.post("https://api.telegram.org/botX:Y/sendMessage").mock(
            return_value=httpx.Response(
                401, json={"ok": False, "description": "Unauthorized"}
            )
        )
        ok = await telegram.send_message(bot_token="X:Y", chat_id="1", text="x")
        assert ok is False


@pytest.mark.asyncio
async def test_send_message_returns_false_on_network_error():
    with respx.mock() as mock:
        mock.post("https://api.telegram.org/botX:Y/sendMessage").mock(
            side_effect=httpx.ConnectError("boom")
        )
        ok = await telegram.send_message(bot_token="X:Y", chat_id="1", text="x")
        assert ok is False


@pytest.mark.asyncio
async def test_get_me_success():
    with respx.mock() as mock:
        mock.get("https://api.telegram.org/botABC:DEF/getMe").mock(
            return_value=httpx.Response(
                200, json={"ok": True, "result": {"username": "trbot"}}
            )
        )
        info = await telegram.get_me("ABC:DEF")
        assert info == {"ok": True, "username": "trbot"}


@pytest.mark.asyncio
async def test_get_me_failure_returns_dict_with_error():
    with respx.mock() as mock:
        mock.get("https://api.telegram.org/botBAD:KEY/getMe").mock(
            return_value=httpx.Response(
                401, json={"ok": False, "description": "Unauthorized"}
            )
        )
        info = await telegram.get_me("BAD:KEY")
        assert info["ok"] is False
        assert "Unauthorized" in info["error"]


@pytest.mark.asyncio
async def test_send_message_returns_false_on_non_json_body():
    """A 200 response whose body is not JSON must not crash the caller."""
    with respx.mock() as mock:
        mock.post("https://api.telegram.org/botX:Y/sendMessage").mock(
            return_value=httpx.Response(200, text="<html>not json</html>")
        )
        ok = await telegram.send_message(bot_token="X:Y", chat_id="1", text="x")
        assert ok is False


@pytest.mark.asyncio
async def test_get_me_returns_false_on_non_json_body():
    """A 200 response whose body is not JSON must yield {ok: False, error: ...}."""
    with respx.mock() as mock:
        mock.get("https://api.telegram.org/botX:Y/getMe").mock(
            return_value=httpx.Response(200, text="<html>oops</html>")
        )
        info = await telegram.get_me("X:Y")
        assert info["ok"] is False
        assert info["error"]


@pytest.mark.asyncio
async def test_get_me_skips_json_parse_on_5xx():
    """A 500 with HTML body must not attempt to JSON-decode."""
    with respx.mock() as mock:
        mock.get("https://api.telegram.org/botX:Y/getMe").mock(
            return_value=httpx.Response(500, text="<html>down</html>")
        )
        info = await telegram.get_me("X:Y")
        assert info["ok"] is False
        assert "500" in info["error"]
