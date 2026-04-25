"""Codex OAuth integration for TradingAgents.

This module is a minimal in-tree adapter inspired by the MIT-licensed
`langchain-codex-oauth` project:
https://github.com/AnthonyTlei/langchain-codex-oauth
"""

from .chat_model import ChatCodexOAuth

__all__ = ["ChatCodexOAuth"]
