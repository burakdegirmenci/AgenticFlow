"""AI prompt node - free-form completion against any LLM provider."""
from typing import Any

from app.engine.context import ExecutionContext
from app.engine.errors import NodeError
from app.engine.node_base import BaseNode
from app.nodes import register
from app.nodes.ai._common import flatten_inputs, render_template
from app.services.llm import LLMProviderError, available_providers, get_provider
from app.services.llm.base import LLMMessage


@register
class AIPromptNode(BaseNode):
    type_id = "ai.prompt"
    category = "ai"
    display_name = "AI Prompt"
    description = "Seçilen LLM sağlayıcıya serbest formda prompt gönderir, yanıtı döner."
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
            "usage": {"type": "object"},
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
                "enum": ["", "anthropic_api", "anthropic_cli", "google_genai"],
            },
            "model": {
                "type": "string",
                "title": "Model",
                "description": "Boş = sağlayıcı default'u",
                "default": "",
            },
            "system": {
                "type": "string",
                "title": "System Prompt",
                "default": "Sen yardımcı bir asistansın.",
            },
            "prompt": {
                "type": "string",
                "title": "Prompt",
                "description": "{{field}} syntax'ı ile input verisine erişebilirsin",
                "default": "",
            },
            "temperature": {
                "type": "number",
                "title": "Temperature",
                "default": 0.7,
                "minimum": 0,
                "maximum": 2,
            },
            "max_tokens": {
                "type": "integer",
                "title": "Max Tokens",
                "default": 2048,
                "minimum": 1,
                "maximum": 16384,
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
        provider_name = (config.get("provider") or "").strip() or None
        try:
            provider = get_provider(provider_name)
        except LLMProviderError as e:
            raise NodeError(
                node_id="",
                node_type=self.type_id,
                message=f"{e}. Available: {available_providers()}",
            )

        merged = flatten_inputs(inputs)
        system = render_template(str(config.get("system", "")), merged)
        prompt = render_template(str(config.get("prompt", "")), merged)
        if not prompt.strip():
            raise NodeError("", self.type_id, "prompt is empty after interpolation")

        try:
            resp = await provider.complete(
                system=system,
                messages=[LLMMessage(role="user", content=prompt)],
                model=(config.get("model") or None),
                temperature=float(config.get("temperature", 0.7)),
                max_tokens=int(config.get("max_tokens", 2048)),
            )
        except LLMProviderError as e:
            raise NodeError("", self.type_id, str(e))

        return {
            "text": resp.text,
            "usage": resp.usage,
            "provider": provider.name,
        }
