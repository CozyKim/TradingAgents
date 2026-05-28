"""Manual ReAct loop for sector graph nodes that bind a single tool.

LangChain's ``bind_tools()`` only lets the model REQUEST tool calls; it does
not execute them. This helper runs the request/execute/respond cycle until
the model returns an AIMessage with no further tool_calls (or the safety
``max_iter`` cap is reached). The SearchBudget guard inside ``web_search``
already caps external API calls; ``max_iter`` only protects against a model
that keeps requesting the tool after the budget has been exhausted.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from langchain_core.messages import AnyMessage, ToolMessage

logger = logging.getLogger(__name__)


def invoke_with_tool_loop(
    chat,
    tool,
    messages: Sequence[AnyMessage],
    *,
    max_iter: int = 8,
) -> tuple[Any, list[AnyMessage]]:
    """Drive a chat-with-tools loop until the model stops requesting tool calls.

    Args:
        chat: LLM already wrapped via ``llm.bind_tools([tool])``.
        tool: The single langchain ``@tool`` callable bound to ``chat``.
            Today the only tool is ``web_search``; expand to a dict lookup
            if more tools are ever bound at once.
        messages: Initial conversation history (system + human prompts).
        max_iter: Safety cap on LLM iterations. Stops a runaway loop if the
            model keeps requesting tools after the per-node budget is
            exhausted (tool returns [] → model retries indefinitely otherwise).

    Returns:
        ``(final_ai_message, full_history)`` — caller reads
        ``final_ai_message.content`` and may inspect the full history.
    """
    history: list[AnyMessage] = list(messages)
    ai: Any = None
    for _ in range(max_iter):
        ai = chat.invoke(history)
        history.append(ai)
        tool_calls = getattr(ai, "tool_calls", None) or []
        if not tool_calls:
            return ai, history
        for tc in tool_calls:
            args = tc["args"] if isinstance(tc, dict) else getattr(tc, "args", {})
            tc_id = tc["id"] if isinstance(tc, dict) else getattr(tc, "id", "")
            try:
                result = tool.invoke(args)
            except Exception:  # noqa: BLE001 — never let a bad tool call crash the graph
                # Models occasionally emit tool_calls with missing/invalid
                # args (e.g. no `query`). Swallow Pydantic/KeyError/etc and
                # feed an empty-result ToolMessage back so the model can
                # recover (likely by giving up on the search and writing
                # the answer from context).
                logger.exception("invoke_with_tool_loop: tool invocation failed")
                result = "[]"
            history.append(ToolMessage(content=str(result), tool_call_id=tc_id))
    return ai, history
