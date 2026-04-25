import json
import tempfile
import unittest
from pathlib import Path

from tradingagents.llm_clients.codex_oauth.auth import (
    build_authorize_url,
    decode_jwt_payload,
    generate_pkce,
)
from tradingagents.llm_clients.codex_oauth.client import (
    CodexBackendClient,
    parse_assistant_message,
)
from tradingagents.llm_clients.codex_oauth.message_conversion import (
    messages_to_codex_request_parts,
    messages_to_input_items,
)
from tradingagents.llm_clients.codex_oauth.store import AuthStore, OAuthCredentials
from tradingagents.llm_clients.codex_oauth.tooling import (
    convert_tools,
    normalize_tool_choice,
)
from tradingagents.llm_clients.factory import create_llm_client
from tradingagents.llm_clients.model_catalog import get_known_models
from tradingagents.llm_clients.validators import validate_model


class CodexOAuthClientTests(unittest.TestCase):
    def test_factory_creates_codex_oauth_client(self):
        client = create_llm_client("codex_oauth", "gpt-5.5")

        self.assertEqual(client.__class__.__name__, "CodexOAuthClient")
        self.assertTrue(client.validate_model())

    def test_catalog_models_are_validator_approved(self):
        known_models = get_known_models()["codex_oauth"]

        self.assertIn("gpt-5.5", known_models)
        self.assertIn("gpt-5.4-mini", known_models)
        self.assertNotIn("gpt-5.2-codex", known_models)
        for model in known_models:
            with self.subTest(model=model):
                self.assertTrue(validate_model("codex_oauth", model))

    def test_supported_gpt5_models_are_sent_to_codex_backend_unchanged(self):
        for model in ("gpt-5.5", "gpt-5.4-mini"):
            with self.subTest(model=model):
                body = CodexBackendClient._build_request_body(
                    input_items=[{"role": "user", "content": "Analyze NVDA"}],
                    model=model,
                    tools=None,
                    tool_choice=None,
                    temperature=None,
                    max_output_tokens=None,
                    reasoning_effort=None,
                    text_verbosity=None,
                    extra_instructions="You are a market analyst.",
                )

                self.assertEqual(body["model"], model)
                self.assertEqual(body["instructions"], "You are a market analyst.")

    def test_convert_tools_outputs_codex_responses_tool_schema(self):
        openai_tool_schema = {
            "type": "function",
            "function": {
                "name": "get_stock_data",
                "description": "Get OHLCV stock data.",
                "parameters": {"type": "object", "properties": {}},
            },
        }

        tools = convert_tools([openai_tool_schema])

        self.assertEqual(
            tools,
            [
                {
                    "type": "function",
                    "name": "get_stock_data",
                    "description": "Get OHLCV stock data.",
                    "parameters": {"type": "object", "properties": {}},
                }
            ],
        )

    def test_normalize_tool_choice_converts_openai_chat_tool_choice(self):
        self.assertEqual(normalize_tool_choice("any"), "required")
        self.assertEqual(
            normalize_tool_choice(
                {"type": "function", "function": {"name": "get_stock_data"}}
            ),
            {"type": "function", "name": "get_stock_data"},
        )

    def test_auth_store_saves_credentials_with_user_only_permissions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            auth_path = Path(temp_dir) / "auth.json"
            store = AuthStore(auth_path)
            creds = OAuthCredentials(
                access="access-token",
                refresh="refresh-token",
                expires=123456789,
                account_id="account-id",
            )

            store.save(creds)

            self.assertEqual(store.load(), creds)
            self.assertEqual(json.loads(auth_path.read_text())["type"], "oauth")
            if auth_path.owner():
                self.assertEqual(auth_path.stat().st_mode & 0o077, 0)

    def test_pkce_and_authorize_url_include_codex_oauth_parameters(self):
        verifier, challenge = generate_pkce()
        url = build_authorize_url(state="state-123", code_challenge=challenge)

        self.assertNotEqual(verifier, challenge)
        self.assertIn("client_id=", url)
        self.assertIn("codex_cli_simplified_flow=true", url)
        self.assertIn("originator=codex_cli_rs", url)
        self.assertIn("state=state-123", url)

    def test_decode_jwt_payload_returns_payload_dict(self):
        token = "header.eyJmb28iOiAiYmFyIn0.signature"

        self.assertEqual(decode_jwt_payload(token), {"foo": "bar"})

    def test_message_conversion_preserves_tool_call_loop_items(self):
        messages = [
            {"role": "user", "content": "Analyze NVDA"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "name": "get_stock_data",
                        "args": {"symbol": "NVDA"},
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "content": "date,close\n2026-01-01,100",
            },
        ]

        self.assertEqual(
            messages_to_input_items(messages),
            [
                {"role": "user", "content": "Analyze NVDA"},
                {
                    "type": "function_call",
                    "call_id": "call_1",
                    "name": "get_stock_data",
                    "arguments": '{"symbol": "NVDA"}',
                },
                {
                    "type": "function_call_output",
                    "call_id": "call_1",
                    "output": "date,close\n2026-01-01,100",
                },
            ],
        )

    def test_message_conversion_moves_system_messages_to_instructions(self):
        instructions, input_items = messages_to_codex_request_parts(
            [
                {"role": "system", "content": "You are a market analyst."},
                {"role": "user", "content": "Analyze NVDA"},
            ]
        )

        self.assertEqual(instructions, "You are a market analyst.")
        self.assertEqual(input_items, [{"role": "user", "content": "Analyze NVDA"}])

    def test_parse_assistant_message_extracts_text_and_tool_calls(self):
        parsed = parse_assistant_message(
            {
                "id": "resp_1",
                "model": "gpt-5.2-codex",
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "Need data"}],
                    },
                    {
                        "type": "function_call",
                        "call_id": "call_1",
                        "name": "get_news",
                        "arguments": '{"query": "NVDA"}',
                    },
                ],
                "usage": {"input_tokens": 10, "output_tokens": 5},
            }
        )

        self.assertEqual(parsed.content, "Need data")
        self.assertEqual(parsed.tool_calls[0]["name"], "get_news")
        self.assertEqual(parsed.tool_calls[0]["args"], {"query": "NVDA"})
        self.assertEqual(parsed.response_metadata["model"], "gpt-5.2-codex")

    def test_complete_uses_output_item_done_when_terminal_response_output_is_empty(self):
        client = _FakeCodexBackendClient(
            [
                {
                    "type": "response.created",
                    "response": {"id": "resp_1", "model": "gpt-5.5", "output": []},
                },
                {
                    "type": "response.output_item.done",
                    "item": {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "Hello!"}],
                    },
                },
                {
                    "type": "response.completed",
                    "response": {"id": "resp_1", "model": "gpt-5.5", "output": []},
                },
            ]
        )

        parsed = client.complete(
            input_items=[{"role": "user", "content": "Say hello."}],
            model="gpt-5.5",
            extra_instructions="You are a helpful assistant.",
        )

        self.assertEqual(parsed.content, "Hello!")

    def test_backend_error_guides_chatgpt_account_model_names(self):
        response = _make_response(
            status_code=400,
            body=(
                '{"detail":"The \'gpt-5.2-codex\' model is not supported '
                'when using Codex with a ChatGPT account."}'
            ),
        )

        error = CodexBackendClient._to_backend_error(response)

        self.assertIn("gpt-5.5", str(error))
        self.assertIn("gpt-5.1-codex-max", str(error))

def _make_response(status_code: int, body: str):
    from requests import Response

    response = Response()
    response.status_code = status_code
    response._content = body.encode("utf-8")
    return response


class _FakeCodexBackendClient(CodexBackendClient):
    def __init__(self, events: list[dict]):
        self._events = events

    def stream_events(self, **kwargs):
        yield from self._events


if __name__ == "__main__":
    unittest.main()
