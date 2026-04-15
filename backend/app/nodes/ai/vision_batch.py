"""Batch AI vision node - iterates over a list of items (e.g. products),
calls vision per item, produces a results array.

Abort policy: if ``abort_on_consecutive_errors`` errors happen in a row,
the whole node raises NodeError and the workflow stops. Resets counter
on a successful call.

Supports Anthropic Claude (URL image sources) and Google Gemini
(downloaded image bytes). Bypasses the LLMProvider abstraction because
LLMMessage.content is str-only.
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
from app.nodes.transform.parse_stok import _resolve_items


class _ImagesUnavailable(Exception):
    """Raised when every image URL for an item fails to download.

    This is a data-quality issue (stale CDN URLs), not an API failure,
    so the vision_batch main loop records the item as skipped and does
    NOT increment the consecutive-error counter used for abort policy.
    """


@register
class AIVisionBatchNode(BaseNode):
    type_id = "ai.vision_batch"
    category = "ai"
    display_name = "AI Vision (Batch)"
    description = (
        "Bir liste üzerinde dönerek her öğe için ayrı vision çağrısı yapar "
        "(ör. her ürün için görsellerden açıklama üretir). "
        "Üst üste N hata olursa flow'u durdurur."
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
            "results": {"type": "array"},
            "success_count": {"type": "integer"},
            "error_count": {"type": "integer"},
            "skipped_count": {"type": "integer"},
            "aborted": {"type": "boolean"},
        },
    }

    config_schema = {
        "type": "object",
        "properties": {
            "items_path": {
                "type": "string",
                "title": "Öğe Listesi Path'i",
                "description": (
                    "Input içinde işlenecek listenin yolu. Boş = parent'ın "
                    "items/urunler/data alanı. Örn: urunler"
                ),
                "default": "",
            },
            "image_path_per_item": {
                "type": "string",
                "title": "Görsel Path (item içinde)",
                "description": (
                    "Her item içindeki görsel URL listesinin yolu. Örn: Resimler.string"
                ),
                "default": "Resimler.string",
            },
            "id_path_per_item": {
                "type": "string",
                "title": "ID Path (item içinde)",
                "description": (
                    "Her item içindeki benzersiz ID'nin yolu. Vision sonucuyla "
                    "eşlemek için kullanılır. Örn: ID veya UrunKartiID"
                ),
                "default": "ID",
            },
            "name_path_per_item": {
                "type": "string",
                "title": "İsim Path (item içinde, opsiyonel)",
                "description": "Prompt'ta {{name}} olarak kullanılır. Örn: UrunAdi",
                "default": "UrunAdi",
            },
            "max_items": {
                "type": "integer",
                "title": "Maks. Öğe Sayısı",
                "description": "0 = hepsi. Kalanlar sonraki çalıştırmada işlenir.",
                "default": 10,
                "minimum": 0,
            },
            "provider": {
                "type": "string",
                "title": "Sağlayıcı",
                "default": "",
                "enum": ["", "anthropic_api", "google_genai"],
            },
            "model": {
                "type": "string",
                "title": "Model",
                "default": "",
            },
            "system": {
                "type": "string",
                "title": "System Prompt",
                "default": (
                    "Sen uzman bir e-ticaret ürün açıklama yazarısın. "
                    "Görselleri dikkatle inceleyip SEO dostu, ikna edici, "
                    "Türkçe ürün açıklamaları üretirsin. "
                    "Sadece açıklamayı döndür, ek açıklama veya yorum yazma."
                ),
            },
            "prompt": {
                "type": "string",
                "title": "Prompt Şablonu",
                "description": (
                    "Her item için render edilir. {{name}} = ürün adı "
                    "(name_path'ten okunur). {{field}} ile diğer item "
                    "alanlarına erişebilirsin."
                ),
                "default": (
                    "Bu ürün görsellerini incele ve Türkçe, satışa yönelik "
                    "bir e-ticaret ürün açıklaması yaz.\n\n"
                    "Ürün adı: {{name}}\n\n"
                    "Format:\n"
                    "- Kısa, çarpıcı 1 cümlelik giriş\n"
                    "- Madde madde 5 özellik (renk, malzeme, stil, "
                    "kullanım alanı, detay)\n"
                    "- Kapanış CTA cümlesi\n\n"
                    "Sadece açıklamayı döndür, ek açıklama yazma."
                ),
            },
            "max_images_per_item": {
                "type": "integer",
                "title": "Ürün Başına Maks. Görsel",
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
            "item_delay_ms": {
                "type": "integer",
                "title": "Öğeler Arası Bekleme (ms)",
                "description": "Rate limit'i azaltmak için her item sonrası bekleme",
                "default": 500,
                "minimum": 0,
                "maximum": 60000,
            },
            "abort_on_consecutive_errors": {
                "type": "integer",
                "title": "Ardışık Hata Eşiği",
                "description": "Bu kadar üst üste hata olursa flow durur",
                "default": 3,
                "minimum": 1,
                "maximum": 100,
            },
        },
        "required": ["prompt"],
    }

    async def execute(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        items = self._resolve_input_items(inputs, config)
        max_items = int(config.get("max_items", 10))
        if max_items > 0:
            items = items[:max_items]

        if not items:
            return {
                "results": [],
                "success_count": 0,
                "error_count": 0,
                "skipped_count": 0,
                "aborted": False,
            }

        # Resolve provider once (same logic as single ai.vision)
        provider_name = self._resolve_provider(config)

        image_path = str(config.get("image_path_per_item", "Resimler.string"))
        id_path = str(config.get("id_path_per_item", "ID"))
        name_path = str(config.get("name_path_per_item", "UrunAdi"))
        max_images = int(config.get("max_images_per_item", 4))
        max_tokens = int(config.get("max_tokens", 1500))
        temperature = float(config.get("temperature", 0.7))
        model_override = (config.get("model") or "").strip() or None
        system_tpl = str(config.get("system", ""))
        prompt_tpl = str(config.get("prompt", ""))
        delay_sec = int(config.get("item_delay_ms", 500)) / 1000.0
        abort_threshold = int(config.get("abort_on_consecutive_errors", 3))

        results: list[dict[str, Any]] = []
        success_count = 0
        error_count = 0
        skipped_count = 0
        consecutive_errors = 0

        for idx, item in enumerate(items):
            item_id = _get_path(item, id_path) if id_path else None
            name = _get_path(item, name_path) if name_path else None
            image_urls_raw = _get_path(item, image_path) if image_path else None
            image_urls = _coerce_urls(image_urls_raw)
            if max_images > 0:
                image_urls = image_urls[:max_images]

            ctx = dict(item) if isinstance(item, dict) else {}
            ctx["name"] = name or ""
            system = render_template(system_tpl, ctx)
            prompt = render_template(prompt_tpl, ctx)

            if not image_urls:
                # No image URLs on the item at all → data quality skip,
                # don't count toward abort threshold.
                results.append(
                    {
                        "index": idx,
                        "urun_karti_id": item_id,
                        "name": name,
                        "success": False,
                        "skipped": True,
                        "reason": f"no image URLs at '{image_path}'",
                        "image_urls": [],
                    }
                )
                skipped_count += 1
                continue

            try:
                text, usage, model = await self._call_provider(
                    provider_name=provider_name,
                    system=system,
                    prompt=prompt,
                    image_urls=image_urls,
                    model_override=model_override,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                results.append(
                    {
                        "index": idx,
                        "urun_karti_id": item_id,
                        "name": name,
                        "success": True,
                        "aciklama": text,
                        "image_urls": image_urls,
                        "image_count": len(image_urls),
                        "model": model,
                        "provider": provider_name,
                        "usage": usage,
                    }
                )
                success_count += 1
                consecutive_errors = 0
            except _ImagesUnavailable as e:
                # All image URLs for this item failed to download.
                # Treat as skipped (stale CDN refs, not a service failure).
                results.append(
                    {
                        "index": idx,
                        "urun_karti_id": item_id,
                        "name": name,
                        "success": False,
                        "skipped": True,
                        "reason": str(e)[:300],
                        "image_urls": image_urls,
                    }
                )
                skipped_count += 1
            except Exception as e:
                results.append(
                    {
                        "index": idx,
                        "urun_karti_id": item_id,
                        "name": name,
                        "success": False,
                        "error": str(e)[:500],
                        "image_urls": image_urls,
                    }
                )
                error_count += 1
                consecutive_errors += 1
                if consecutive_errors >= abort_threshold:
                    return self._abort_result(results, success_count, error_count, skipped_count)

            if delay_sec > 0 and idx < len(items) - 1:
                await asyncio.sleep(delay_sec)

        return {
            "results": results,
            "success_count": success_count,
            "error_count": error_count,
            "skipped_count": skipped_count,
            "aborted": False,
        }

    # ------------------------------------------------------------------
    def _abort_result(
        self,
        results: list[dict[str, Any]],
        success_count: int,
        error_count: int,
        skipped_count: int,
    ) -> dict[str, Any]:
        """Raise NodeError with partial results attached in the message."""
        last_errors = [r.get("error", "?") for r in results[-3:] if r.get("error")]
        raise NodeError(
            "",
            self.type_id,
            f"Aborted: consecutive error threshold exceeded. "
            f"success={success_count}, error={error_count}, "
            f"skipped={skipped_count}. "
            f"Last errors: {last_errors}",
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_input_items(inputs: dict[str, Any], config: dict[str, Any]) -> list[Any]:
        """Resolve the list of items to iterate over.

        Priority:
          1. Explicit ``items_path`` config (dotted path into flattened inputs)
          2. Standard upstream keys (items/urunler/data) via _resolve_items
        """
        items_path = str(config.get("items_path", "")).strip()
        if items_path:
            merged = flatten_inputs(inputs)
            val = _get_path(merged, items_path)
            if isinstance(val, list):
                return val
            # Sometimes the path returns the parent dict with {"items": [...]}
            if isinstance(val, dict) and "items" in val:
                inner = val["items"]
                if isinstance(inner, list):
                    return inner
            return []
        return _resolve_items(inputs, "")

    @staticmethod
    def _resolve_provider(config: dict[str, Any]) -> str:
        from app.services.settings_service import get_llm_setting

        provider_name = (config.get("provider") or "").strip()
        if not provider_name:
            provider_name = (get_llm_setting("LLM_PROVIDER") or "").strip()
        if provider_name in ("", "anthropic_cli"):
            if get_llm_setting("ANTHROPIC_API_KEY"):
                return "anthropic_api"
            if get_llm_setting("GOOGLE_API_KEY"):
                return "google_genai"
            raise NodeError(
                "",
                "ai.vision_batch",
                "No vision-capable provider configured. Set "
                "ANTHROPIC_API_KEY or GOOGLE_API_KEY in Settings.",
            )
        return provider_name

    async def _call_provider(
        self,
        provider_name: str,
        system: str,
        prompt: str,
        image_urls: list[str],
        model_override: str | None,
        max_tokens: int,
        temperature: float,
    ) -> tuple[str, dict[str, Any], str]:
        if provider_name == "anthropic_api":
            return await self._call_anthropic(
                system, prompt, image_urls, model_override, max_tokens, temperature
            )
        if provider_name == "google_genai":
            return await self._call_gemini(
                system, prompt, image_urls, model_override, max_tokens, temperature
            )
        raise NodeError(
            "",
            self.type_id,
            f"Provider '{provider_name}' does not support vision",
        )

    async def _call_anthropic(
        self,
        system: str,
        prompt: str,
        image_urls: list[str],
        model_override: str | None,
        max_tokens: int,
        temperature: float,
    ) -> tuple[str, dict[str, Any], str]:
        from anthropic import AsyncAnthropic

        from app.services.settings_service import get_llm_setting

        api_key = get_llm_setting("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY missing")

        model = model_override or get_llm_setting("CLAUDE_MODEL_NODE") or "claude-opus-4-6"
        client = AsyncAnthropic(api_key=api_key)
        content_blocks: list[dict[str, Any]] = [
            {"type": "image", "source": {"type": "url", "url": url}} for url in image_urls
        ]
        content_blocks.append({"type": "text", "text": prompt})

        resp = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system or "You are a helpful assistant.",
            messages=[{"role": "user", "content": content_blocks}],
        )
        text = "".join(
            getattr(b, "text", "") for b in resp.content if getattr(b, "type", None) == "text"
        )
        usage: dict[str, Any] = {}
        if getattr(resp, "usage", None):
            usage = {
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
            }
        return text, usage, model

    async def _call_gemini(
        self,
        system: str,
        prompt: str,
        image_urls: list[str],
        model_override: str | None,
        max_tokens: int,
        temperature: float,
    ) -> tuple[str, dict[str, Any], str]:
        import httpx
        from google import genai
        from google.genai import types as genai_types

        from app.services.settings_service import get_llm_setting

        api_key = get_llm_setting("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY missing")

        model = model_override or get_llm_setting("GEMINI_MODEL_NODE") or "gemini-2.5-flash"

        async def fetch(url: str) -> tuple[bytes, str] | None:
            try:
                async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as http:
                    r = await http.get(url)
                    r.raise_for_status()
                    mime = r.headers.get("content-type", "").split(";")[0].strip()
                    if not mime or not mime.startswith("image/"):
                        guessed, _ = mimetypes.guess_type(url)
                        mime = guessed or "image/jpeg"
                    return r.content, mime
            except Exception:
                # Broken / missing image URL — skip this one, try the rest.
                return None

        raw = await asyncio.gather(*(fetch(u) for u in image_urls))
        results = [r for r in raw if r is not None]
        if not results:
            # Special marker — vision_batch main loop treats this as a
            # per-item skip, not an API error, so the abort counter for
            # real service failures stays clean.
            raise _ImagesUnavailable(f"all {len(image_urls)} image URLs failed to fetch")
        client = genai.Client(api_key=api_key)
        parts: list[Any] = [
            genai_types.Part.from_bytes(data=data, mime_type=mime) for data, mime in results
        ]
        parts.append(genai_types.Part.from_text(text=prompt))
        contents = [genai_types.Content(role="user", parts=parts)]

        cfg_kwargs: dict[str, Any] = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
            "system_instruction": system or None,
        }
        try:
            cfg_kwargs["thinking_config"] = genai_types.ThinkingConfig(thinking_budget=0)
        except Exception:
            pass
        cfg = genai_types.GenerateContentConfig(**cfg_kwargs)

        resp = await client.aio.models.generate_content(model=model, contents=contents, config=cfg)
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


# ---------------------------------------------------------------------------
def _coerce_urls(raw: Any) -> list[str]:
    """Normalize various shapes into a flat list of http(s) URLs."""
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw] if raw.startswith("http") else []
    if isinstance(raw, list):
        return [str(x) for x in raw if isinstance(x, str) and x.startswith("http")]
    if isinstance(raw, dict):
        for key in ("string", "item", "items", "urls"):
            if key in raw:
                return _coerce_urls(raw[key])
    return []
