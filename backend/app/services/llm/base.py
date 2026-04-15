"""LLM Provider base class + shared types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


class LLMProviderError(Exception):
    """Provider is misconfigured, unavailable, or returned an error."""


@dataclass
class LLMMessage:
    """Canonical message shape passed to all providers."""

    role: str  # "user" | "assistant"
    content: str  # plain text; tool results are encoded into text for simplicity


@dataclass
class LLMResponse:
    """Non-streaming completion response."""

    text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)
    stop_reason: str | None = None


@dataclass
class LLMEvent:
    """Streaming event.

    Types:
      - message_start: {}
      - text_delta:    {"text": "..."}
      - tool_use:      {"id": "...", "name": "...", "input": {...}}
      - usage:         {"input_tokens": N, "output_tokens": N}
      - error:         {"message": "..."}
      - done:          {"stop_reason": "end_turn"}
    """

    type: str
    data: dict[str, Any] = field(default_factory=dict)


class LLMProvider(ABC):
    """Abstract base for all LLM backends."""

    name: str = ""
    display_name: str = ""
    supports_tools: bool = True
    supports_streaming: bool = True
    default_model: str = ""

    @abstractmethod
    async def is_available(self) -> tuple[bool, str]:
        """Return (available, reason). `reason` is a short human note."""

    @abstractmethod
    async def complete(
        self,
        system: str,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """One-shot completion (non-streaming)."""

    @abstractmethod
    def stream(
        self,
        system: str,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[LLMEvent]:
        """Streaming completion. Returns an async iterator of LLMEvent objects.

        NOTE: declared as a plain ``def`` returning ``AsyncIterator`` rather
        than ``async def`` so subclasses can be defined as async generators
        (``async def ...: yield``). That is the canonical Python way to type
        an async-generator-producing factory without forcing callers to
        ``await`` before ``async for``-iterating.
        """
