"""AI vision node - sends images + prompt to a vision-capable LLM.

Supports both Anthropic Claude (via SDK, URL image sources) and Google
Gemini (via google-genai SDK, downloaded bytes). Bypasses the LLMProvider
abstraction because LLMMessage.content is str-only and does not model
image content blocks.
"""
from __future__ import annotations

import asyncio
import mimetypes
from typing import Any

from app.engine.context import ExecutionContext
from app.engine.errors import NodeError
from app.engine.node_base import BaseNode
from app.nodes import register
from app.nodes.ai._common import _get_path, flatten_inputs, render_template


@register
class AIVisionNode(BaseNode):
    type_id = "ai.vision"
    category = "ai"
    display_name = "AI Vision"
    description = (
        "Bir veya daha fazla görseli vision-destekli bir LLM'e gönderir ve "
        "istenen formatta metin üretir. Ürün fotoğraflarından açıklama "
        "çıkarma gibi işler için kullanılır. Anthropic ve Google Gemini destekli."
    )
    icon = "sparkles"
    color = "#2563EB"

    input_schema = {
        "type": "object",
        "properties": {"items": {"type": "array"}},
    }

    output_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "image_count": {"type": "integer"},
            "usage": {"type": "object"},
            "model": {"type": "string"},
            "provider": {"type": "string"},
        },
    }

    config_schema = {
        "type": "object",
        "properties": {
            "provider": {
                "type": "string",
                "title": "Sağlayıcı",
                "description": "Boş = global default (Settings)",
                "default": "",
                "enum": ["", "anthropic_api", "google_genai"],
            },
            "model": {
                "type": "string",
                "title": "Model",
                "description": "Boş = sağlayıcı default'u (Opus 4.6 / Gemini 2.5 Flash)",
                "default": "",
            },
            "image_urls_path": {
                "type": "string",
                "title": "Görsel URL Path'i",
                "description": (
                    "Input içinde görsel URL'lerinin bulunduğu path. "
                    "Örn: urunler.0.Resimler.string (liste veya tek string olabilir)"
                ),
                "default": "urunler.0.Resimler.string",
            },
            "system": {
                "type": "string",
                "title": "System Prompt",
                "default": (
                    "Sen uzman bir e-ticaret ürün açıklama yazarısın. "
                    "Görselleri inceleyip SEO dostu, ikna edici, Türkçe ürün "
                    "açıklamaları üretirsin."
                ),
            },
            "prompt": {
                "type": "string",
                "title": "Kullanıcı Prompt'u",
                "description": (
                    "{{field}} syntax'ı ile input'a erişebilirsin. "
                    "Örn: {{urunler.0.UrunAdi}}"
                ),
                "default": (
                    "Bu ürün görselleri için SEO uyumlu, satışa yönelik bir ürün "
                    "açıklaması yaz. Ürün adı: {{urunler.0.UrunAdi}}. "
                    "Kısa giriş + madde madde 5 özellik + kapanış şeklinde olsun. "
                    "Renk, malzeme, stil gibi detayları görsellerden oku."
                ),
            },
            "max_images": {
                "type": "integer",
                "title": "Maks. Görsel Sayısı",
                "description": "Maliyet kontrolü için üst sınır",
                "default": 4,
                "minimum": 1,
                "maximum": 20,
            },
            "max_tokens": {
                "type": "integer",
                "title": "Max Tokens",
                "default": 1500,
                "minimum": 1,
                "maximum": 16384,
            },
            "temperature": {
                "type": "number",
                "title": "Temperature",
                "default": 0.7,
                "minimum": 0,
                "maximum": 2,
            },
        },
        "required": ["prompt", "image_urls_path"],
    }

    async def execute(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        merged = flatten_inputs(inputs)

        # 1. Resolve image URLs from the configured path
        path = str(config.get("image_urls_path", "")).strip()
        if not path:
            raise NodeError("", self.type_id, "image_urls_path is empty")

        raw = _get_path(merged, path)
        image_urls = self._coerce_urls(raw)
        if not image_urls:
            raise NodeError(
                "",
                self.type_id,
                f"No image URLs found at path '{path}'. "
                f"Resolved value: {type(raw).__name__}",
            )

        max_images = int(config.get("max_images", 4))
        if max_images > 0:
            image_urls = image_urls[:max_images]

        # 2. Render prompt templates
        system = render_template(str(config.get("system", "")), merged)
        prompt = render_template(str(config.get("prompt", "")), merged)
        if not prompt.strip():
            raise NodeError("", self.type_id, "prompt is empty after interpolation")

        # 3. Pick a provider (config override > global default)
        from app.services.settings_service import get_llm_setting

        provider_name = (config.get("provider") or "").strip()
        if not provider_name:
            provider_name = (get_llm_setting("LLM_PROVIDER") or "").strip()
        # anthropic_cli does not support image content blocks, fall back to API
        if provider_name in ("", "anthropic_cli"):
            if get_llm_setting("ANTHROPIC_API_KEY"):
                provider_name = "anthropic_api"
            elif get_llm_setting("GOOGLE_API_KEY"):
                provider_name = "google_genai"
            else:
                raise NodeError(
                    "",
                    self.type_id,
                    "No vision-capable provider configured. Set "
                    "ANTHROPIC_API_KEY or GOOGLE_API_KEY in Settings.",
                )

        max_tokens = int(config.get("max_tokens", 1500))
        temperature = float(config.get("temperature", 0.7))
        model_override = (config.get("model") or "").strip() or None

        if provider_name == "anthropic_api":
            text, usage, chosen_model = await self._call_anthropic(
                system=system,
                prompt=prompt,
                image_urls=image_urls,
                model_override=model_override,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        elif provider_name == "google_genai":
            text, usage, chosen_model = await self._call_gemini(
                system=system,
                prompt=prompt,
                image_urls=image_urls,
                model_override=model_override,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        else:
            raise NodeError(
                "",
                self.type_id,
                f"Provider '{provider_name}' does not support vision. "
                f"Use anthropic_api or google_genai.",
            )

        return {
            "text": text,
            "image_count": len(image_urls),
            "image_urls": image_urls,
            "usage": usage,
            "model": chosen_model,
            "provider": provider_name,
        }

    # ------------------------------------------------------------------
    # Provider implementations
    # ------------------------------------------------------------------
    async def _call_anthropic(
        self,
        system: str,
        prompt: str,
        image_urls: list[str],
        model_override: str | None,
        max_tokens: int,
        temperature: float,
    ) -> tuple[str, dict[str, Any], str]:
        from app.services.settings_service import get_llm_setting

        api_key = get_llm_setting("ANTHROPIC_API_KEY")
        if not api_key:
            raise NodeError(
                "",
                self.type_id,
                "ANTHROPIC_API_KEY is not configured. Add it in Settings or .env.",
            )
        try:
            from anthropic import AsyncAnthropic
        except ImportError as e:
            raise NodeError("", self.type_id, f"anthropic SDK not installed: {e}")

        model = (
            model_override
            or get_llm_setting("CLAUDE_MODEL_NODE")
            or "claude-opus-4-6"
        )

        client = AsyncAnthropic(api_key=api_key)
        content_blocks: list[dict[str, Any]] = [
            {"type": "image", "source": {"type": "url", "url": url}}
            for url in image_urls
        ]
        content_blocks.append({"type": "text", "text": prompt})

        try:
            resp = await client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system or "You are a helpful assistant.",
                messages=[{"role": "user", "content": content_blocks}],
            )
        except Exception as e:
            raise NodeError("", self.type_id, f"Anthropic vision call failed: {e}")

        text_parts = [
            getattr(b, "text", "")
            for b in resp.content
            if getattr(b, "type", None) == "text"
        ]
        usage: dict[str, Any] = {}
        if getattr(resp, "usage", None):
            usage = {
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
            }
        return "".join(text_parts), usage, model

    async def _call_gemini(
        self,
        system: str,
        prompt: str,
        image_urls: list[str],
        model_override: str | None,
        max_tokens: int,
        temperature: float,
    ) -> tuple[str, dict[str, Any], str]:
        from app.services.settings_service import get_llm_setting

        api_key = get_llm_setting("GOOGLE_API_KEY")
        if not api_key:
            raise NodeError(
                "",
                self.type_id,
                "GOOGLE_API_KEY is not configured. Add it in Settings or .env.",
            )
        try:
            from google import genai
            from google.genai import types as genai_types
        except ImportError as e:
            raise NodeError("", self.type_id, f"google-genai not installed: {e}")

        model = (
            model_override
            or get_llm_setting("GEMINI_MODEL_NODE")
            or "gemini-2.5-flash"
        )

        # Fetch image bytes in parallel
        try:
            import httpx
        except ImportError as e:
            raise NodeError("", self.type_id, f"httpx not installed: {e}")

        async def fetch(url: str) -> tuple[bytes, str]:
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=30.0
            ) as http:
                r = await http.get(url)
                r.raise_for_status()
                mime = r.headers.get("content-type", "").split(";")[0].strip()
                if not mime or not mime.startswith("image/"):
                    guessed, _ = mimetypes.guess_type(url)
                    mime = guessed or "image/jpeg"
                return r.content, mime

        try:
            results = await asyncio.gather(*(fetch(u) for u in image_urls))
        except Exception as e:
            raise NodeError("", self.type_id, f"Image fetch failed: {e}")

        client = genai.Client(api_key=api_key)

        parts: list[Any] = [
            genai_types.Part.from_bytes(data=data, mime_type=mime)
            for data, mime in results
        ]
        parts.append(genai_types.Part.from_text(text=prompt))
        contents = [genai_types.Content(role="user", parts=parts)]

        cfg_kwargs: dict[str, Any] = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
            "system_instruction": system or None,
        }
        # Gemini 2.5 Flash uses reasoning tokens by default which eats into
        # max_output_tokens. Disable thinking so we get the full text budget.
        try:
            cfg_kwargs["thinking_config"] = genai_types.ThinkingConfig(
                thinking_budget=0
            )
        except Exception:
            pass  # Older SDK: ignore
        cfg = genai_types.GenerateContentConfig(**cfg_kwargs)

        try:
            resp = await client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=cfg,
            )
        except Exception as e:
            raise NodeError("", self.type_id, f"Gemini vision call failed: {e}")

        text_parts: list[str] = []
        for candidate in resp.candidates or []:
            content = getattr(candidate, "content", None)
            if not content:
                continue
            for part in getattr(content, "parts", []) or []:
                t = getattr(part, "text", None)
                if t:
                    text_parts.append(t)

        usage: dict[str, Any] = {}
        meta = getattr(resp, "usage_metadata", None)
        if meta:
            usage = {
                "input_tokens": getattr(meta, "prompt_token_count", 0),
                "output_tokens": getattr(meta, "candidates_token_count", 0),
            }
        return "".join(text_parts), usage, model

    # ------------------------------------------------------------------
    @staticmethod
    def _coerce_urls(raw: Any) -> list[str]:
        """Normalize various Ticimax / user shapes into a flat URL list.

        Accepts:
          - list[str]               -> itself
          - str                     -> [str]
          - dict with "string" key  -> use that list (zeep <string> wrapper)
          - dict with "item" key    -> use that list
        """
        if raw is None:
            return []
        if isinstance(raw, str):
            return [raw] if raw.startswith("http") else []
        if isinstance(raw, list):
            return [str(x) for x in raw if isinstance(x, str) and x.startswith("http")]
        if isinstance(raw, dict):
            for key in ("string", "item", "items", "urls"):
                if key in raw:
                    return AIVisionNode._coerce_urls(raw[key])
        return []
