"""TradingAgents LLM client wrapper for Codex OAuth."""

from __future__ import annotations

from typing import Any

from .base_client import BaseLLMClient
from .codex_oauth import ChatCodexOAuth
from .validators import validate_model


class CodexOAuthClient(BaseLLMClient):
    """Client for ChatGPT/Codex OAuth backed local workflows."""

    provider = "codex_oauth"

    def __init__(self, model: str, base_url: str | None = None, **kwargs: Any):
        """Initialize the Codex OAuth client."""
        super().__init__(model, base_url, **kwargs)

    def get_llm(self) -> Any:
        """Return a LangChain-compatible Codex OAuth chat model."""
        self.warn_if_unknown_model()
        llm_kwargs = {
            "model": self.model,
            "timeout": self.kwargs.get("timeout", 60.0),
            "max_retries": self.kwargs.get("max_retries", 2),
        }
        for key in (
            "reasoning_effort",
            "temperature",
            "max_tokens",
            "text_verbosity",
            "auth_path",
            "extra_instructions",
        ):
            if key in self.kwargs and self.kwargs[key] is not None:
                llm_kwargs[key] = self.kwargs[key]
        return ChatCodexOAuth(**llm_kwargs)

    def validate_model(self) -> bool:
        """Validate the Codex OAuth model name."""
        return validate_model(self.provider, self.model)
