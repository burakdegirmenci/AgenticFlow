"""Anthropic API provider (official SDK, API key)."""
from __future__ import annotations

from typing import Any, AsyncIterator

from app.services.llm import register
from app.services.llm.base import (
    LLMEvent,
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMResponse,
)


@register
class AnthropicAPIProvider(LLMProvider):
    name = "anthropic_api"
    display_name = "Anthropic API"
    supports_tools = True
    supports_streaming = True
    default_model = "claude-opus-4-6"

    def _client(self):
        from app.services.settings_service import get_llm_setting

        key = get_llm_setting("ANTHROPIC_API_KEY")
        if not key:
            raise LLMProviderError(
                "ANTHROPIC_API_KEY is not configured. Add it in Settings or .env."
            )
        try:
            from anthropic import AsyncAnthropic
        except ImportError as e:
            raise LLMProviderError(f"anthropic SDK not installed: {e}")
        return AsyncAnthropic(api_key=key)

    async def is_available(self) -> tuple[bool, str]:
        from app.services.settings_service import get_llm_setting

        if not get_llm_setting("ANTHROPIC_API_KEY"):
            return False, "ANTHROPIC_API_KEY missing"
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False, "anthropic package not installed"
        return True, "ready"

    def _build_params(
        self,
        system: str,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None,
        model: str | None,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        from app.services.settings_service import get_llm_setting

        params: dict[str, Any] = {
            "model": model or get_llm_setting("CLAUDE_MODEL_AGENT") or self.default_model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system or "You are a helpful assistant.",
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if tools:
            params["tools"] = tools
        return params

    async def complete(
        self,
        system: str,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        client = self._client()
        params = self._build_params(system, messages, tools, model, temperature, max_tokens)
        try:
            resp = await client.messages.create(**params)
        except Exception as e:
            raise LLMProviderError(f"Anthropic API error: {e}") from e

        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        for block in resp.content:
            btype = getattr(block, "type", None)
            if btype == "text":
                text_parts.append(getattr(block, "text", ""))
            elif btype == "tool_use":
                tool_calls.append(
                    {
                        "id": getattr(block, "id", ""),
                        "name": getattr(block, "name", ""),
                        "input": getattr(block, "input", {}),
                    }
                )
        usage = {}
        if getattr(resp, "usage", None):
            usage = {
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
            }
        return LLMResponse(
            text="".join(text_parts),
            tool_calls=tool_calls,
            usage=usage,
            stop_reason=getattr(resp, "stop_reason", None),
        )

    async def stream(
        self,
        system: str,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[LLMEvent]:
        client = self._client()
        params = self._build_params(system, messages, tools, model, temperature, max_tokens)

        # Track tool_use blocks being assembled
        current_tool: dict[str, Any] | None = None
        current_tool_json = ""

        try:
            async with client.messages.stream(**params) as stream:
                yield LLMEvent("message_start", {})
                async for event in stream:
                    etype = getattr(event, "type", None)

                    if etype == "content_block_start":
                        block = getattr(event, "content_block", None)
                        if block and getattr(block, "type", None) == "tool_use":
                            current_tool = {
                                "id": getattr(block, "id", ""),
                                "name": getattr(block, "name", ""),
                                "input": {},
                            }
                            current_tool_json = ""

                    elif etype == "content_block_delta":
                        delta = getattr(event, "delta", None)
                        dtype = getattr(delta, "type", None) if delta else None
                        if dtype == "text_delta":
                            yield LLMEvent(
                                "text_delta",
                                {"text": getattr(delta, "text", "")},
                            )
                        elif dtype == "input_json_delta" and current_tool is not None:
                            current_tool_json += getattr(delta, "partial_json", "")

                    elif etype == "content_block_stop":
                        if current_tool is not None:
                            import json

                            try:
                                current_tool["input"] = (
                                    json.loads(current_tool_json)
                                    if current_tool_json
                                    else {}
                                )
                            except json.JSONDecodeError:
                                current_tool["input"] = {"_raw": current_tool_json}
                            yield LLMEvent("tool_use", current_tool)
                            current_tool = None
                            current_tool_json = ""

                    elif etype == "message_delta":
                        usage = getattr(event, "usage", None)
                        if usage is not None:
                            yield LLMEvent(
                                "usage",
                                {
                                    "output_tokens": getattr(usage, "output_tokens", 0),
                                },
                            )

                final = await stream.get_final_message()
                yield LLMEvent(
                    "done",
                    {"stop_reason": getattr(final, "stop_reason", None)},
                )
        except LLMProviderError:
            raise
        except Exception as e:
            yield LLMEvent("error", {"message": f"Anthropic stream error: {e}"})
