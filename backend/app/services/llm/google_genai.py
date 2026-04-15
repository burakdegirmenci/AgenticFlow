"""Google Gemini provider via google-genai SDK (API key)."""
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


# Keys we strip from JSON Schemas before passing to Gemini's FunctionDeclaration
# (Gemini's Schema type has a smaller surface than JSON Schema / Anthropic).
_GEMINI_DROP_KEYS = frozenset(
    {
        "additionalProperties",
        "$schema",
        "definitions",
        "$defs",
        "$ref",
        "examples",
        "default",
        "const",
        "patternProperties",
    }
)


def _sanitize_schema_for_gemini(schema: Any) -> Any:
    """Recursively rewrite a JSON Schema to fit Gemini's Schema validator.

    Key rewrites:
    - `type: ["X", "null"]`  → `type: "X", nullable: true`
    - `type: [...]` (no null) → keep first non-null primitive
    - Drop unsupported keywords (additionalProperties, $schema, $ref, etc.)
    - Recurse into properties / items / anyOf
    """
    if not isinstance(schema, dict):
        return schema

    out: dict[str, Any] = {}
    for key, value in schema.items():
        if key in _GEMINI_DROP_KEYS:
            continue
        if key == "type" and isinstance(value, list):
            non_null = [t for t in value if t != "null"]
            has_null = "null" in value
            if non_null:
                out["type"] = non_null[0]
            else:
                out["type"] = "string"
            if has_null:
                out["nullable"] = True
            continue
        if key == "properties" and isinstance(value, dict):
            out["properties"] = {
                k: _sanitize_schema_for_gemini(v) for k, v in value.items()
            }
            continue
        if key == "items":
            out["items"] = _sanitize_schema_for_gemini(value)
            continue
        if key in ("anyOf", "oneOf", "allOf") and isinstance(value, list):
            # Gemini doesn't really support unions; pick first non-null branch.
            cleaned = [
                _sanitize_schema_for_gemini(s)
                for s in value
                if isinstance(s, dict) and s.get("type") != "null"
            ]
            if cleaned:
                # Merge keys from the first branch into the parent schema.
                first = cleaned[0]
                for fk, fv in first.items():
                    out.setdefault(fk, fv)
                # Mark nullable if any branch was null
                if any(
                    isinstance(s, dict) and s.get("type") == "null" for s in value
                ):
                    out["nullable"] = True
            continue
        out[key] = value

    return out


@register
class GoogleGenAIProvider(LLMProvider):
    name = "google_genai"
    display_name = "Google Gemini"
    supports_tools = True
    supports_streaming = True
    default_model = "gemini-2.5-flash"

    def _client(self):
        from app.services.settings_service import get_llm_setting

        key = get_llm_setting("GOOGLE_API_KEY")
        if not key:
            raise LLMProviderError(
                "GOOGLE_API_KEY is not configured. Add it in Settings or .env."
            )
        try:
            from google import genai
        except ImportError as e:
            raise LLMProviderError(f"google-genai not installed: {e}")
        return genai.Client(api_key=key)

    async def is_available(self) -> tuple[bool, str]:
        from app.services.settings_service import get_llm_setting

        if not get_llm_setting("GOOGLE_API_KEY"):
            return False, "GOOGLE_API_KEY missing"
        try:
            from google import genai  # noqa: F401
        except ImportError:
            return False, "google-genai package not installed"
        return True, "ready"

    def _convert_messages(self, messages: list[LLMMessage]) -> list[dict[str, Any]]:
        """Convert canonical messages to Gemini `contents` format."""
        out: list[dict[str, Any]] = []
        for m in messages:
            role = "model" if m.role == "assistant" else "user"
            out.append({"role": role, "parts": [{"text": m.content}]})
        return out

    def _convert_tools(self, tools: list[dict[str, Any]] | None) -> Any:
        """Convert Anthropic-style tool schemas to Gemini Tool(function_declarations)."""
        if not tools:
            return None
        from google.genai import types as genai_types

        declarations = []
        for tool in tools:
            schema = tool.get("input_schema", {"type": "object"})
            declarations.append(
                genai_types.FunctionDeclaration(
                    name=tool["name"],
                    description=tool.get("description", ""),
                    parameters=_sanitize_schema_for_gemini(schema),
                )
            )
        return [genai_types.Tool(function_declarations=declarations)]

    def _build_config(
        self,
        system: str,
        tools: list[dict[str, Any]] | None,
        temperature: float,
        max_tokens: int,
    ) -> Any:
        from google.genai import types as genai_types

        cfg_kwargs: dict[str, Any] = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        if system:
            cfg_kwargs["system_instruction"] = system
        gtools = self._convert_tools(tools)
        if gtools is not None:
            cfg_kwargs["tools"] = gtools
        return genai_types.GenerateContentConfig(**cfg_kwargs)

    async def complete(
        self,
        system: str,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        from app.services.settings_service import get_llm_setting

        client = self._client()
        contents = self._convert_messages(messages)
        config = self._build_config(system, tools, temperature, max_tokens)
        chosen_model = model or get_llm_setting("GEMINI_MODEL_AGENT") or self.default_model
        try:
            resp = await client.aio.models.generate_content(
                model=chosen_model,
                contents=contents,
                config=config,
            )
        except Exception as e:
            raise LLMProviderError(f"Gemini API error: {e}") from e

        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        for candidate in resp.candidates or []:
            content = getattr(candidate, "content", None)
            if not content:
                continue
            for part in getattr(content, "parts", []) or []:
                if getattr(part, "text", None):
                    text_parts.append(part.text)
                fc = getattr(part, "function_call", None)
                if fc:
                    tool_calls.append(
                        {
                            "id": getattr(fc, "id", "") or fc.name,
                            "name": fc.name,
                            "input": dict(fc.args or {}),
                        }
                    )

        usage: dict[str, Any] = {}
        meta = getattr(resp, "usage_metadata", None)
        if meta:
            usage = {
                "input_tokens": getattr(meta, "prompt_token_count", 0),
                "output_tokens": getattr(meta, "candidates_token_count", 0),
            }
        return LLMResponse(
            text="".join(text_parts),
            tool_calls=tool_calls,
            usage=usage,
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
        from app.services.settings_service import get_llm_setting

        client = self._client()
        contents = self._convert_messages(messages)
        config = self._build_config(system, tools, temperature, max_tokens)
        chosen_model = model or get_llm_setting("GEMINI_MODEL_AGENT") or self.default_model
        try:
            yield LLMEvent("message_start", {})
            async for chunk in await client.aio.models.generate_content_stream(
                model=chosen_model,
                contents=contents,
                config=config,
            ):
                for candidate in chunk.candidates or []:
                    content = getattr(candidate, "content", None)
                    if not content:
                        continue
                    for part in getattr(content, "parts", []) or []:
                        text = getattr(part, "text", None)
                        if text:
                            yield LLMEvent("text_delta", {"text": text})
                        fc = getattr(part, "function_call", None)
                        if fc:
                            yield LLMEvent(
                                "tool_use",
                                {
                                    "id": getattr(fc, "id", "") or fc.name,
                                    "name": fc.name,
                                    "input": dict(fc.args or {}),
                                },
                            )
            yield LLMEvent("done", {"stop_reason": "end_turn"})
        except LLMProviderError:
            raise
        except Exception as e:
            yield LLMEvent("error", {"message": f"Gemini stream error: {e}"})
