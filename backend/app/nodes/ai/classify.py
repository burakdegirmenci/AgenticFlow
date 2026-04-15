"""AI classify node - constrained text classification into a fixed label set."""
from typing import Any

from app.engine.context import ExecutionContext
from app.engine.errors import NodeError
from app.engine.node_base import BaseNode
from app.nodes import register
from app.nodes.ai._common import flatten_inputs, render_template
from app.services.llm import LLMProviderError, get_provider
from app.services.llm.base import LLMMessage


@register
class AIClassifyNode(BaseNode):
    type_id = "ai.classify"
    category = "ai"
    display_name = "AI Sınıflandır"
    description = "Metni verilen etiketlerden birine sınıflandırır. Destek ticket triage için ideal."
    icon = "tag"
    color = "#2563EB"

    input_schema = {"type": "object", "properties": {"text": {"type": "string"}}}

    output_schema = {
        "type": "object",
        "properties": {
            "category": {"type": "string"},
            "confidence": {"type": "number"},
            "reasoning": {"type": "string"},
        },
    }

    config_schema = {
        "type": "object",
        "properties": {
            "provider": {
                "type": "string",
                "title": "Sağlayıcı",
                "default": "",
                "enum": ["", "anthropic_api", "anthropic_cli", "google_genai"],
            },
            "model": {
                "type": "string",
                "title": "Model",
                "default": "",
            },
            "text_template": {
                "type": "string",
                "title": "Sınıflandırılacak Metin",
                "description": "{{field}} ile input'tan değer al",
                "default": "{{text}}",
            },
            "labels": {
                "type": "string",
                "title": "Etiketler",
                "description": "Virgülle ayrılmış etiket listesi (örn: iade,kargo,odeme,diger)",
                "default": "",
            },
            "instructions": {
                "type": "string",
                "title": "Ek Talimat",
                "default": "",
            },
        },
        "required": ["labels"],
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
            raise NodeError("", self.type_id, str(e))

        labels_raw = str(config.get("labels", ""))
        labels = [l.strip() for l in labels_raw.split(",") if l.strip()]
        if not labels:
            raise NodeError("", self.type_id, "labels is required")

        merged = flatten_inputs(inputs)
        text = render_template(str(config.get("text_template", "{{text}}")), merged)
        instructions = str(config.get("instructions", "")).strip()

        system = (
            "Sen bir metin sınıflandırma uzmanısın. Verilen metni SADECE "
            "listedeki etiketlerden biriyle sınıflandır.\n"
            f"Etiketler: {', '.join(labels)}\n"
            "Yanıtını tam olarak şu JSON formatında ver:\n"
            '{"category": "<etiket>", "confidence": 0.0-1.0, "reasoning": "<kısa>"}\n'
            "Sadece JSON döndür, başka hiçbir şey yazma."
        )
        if instructions:
            system += "\n\nEk talimat: " + instructions

        try:
            resp = await provider.complete(
                system=system,
                messages=[LLMMessage(role="user", content=text)],
                model=(config.get("model") or None),
                temperature=0.1,
                max_tokens=512,
            )
        except LLMProviderError as e:
            raise NodeError("", self.type_id, str(e))

        # Parse JSON out of response (robust to code-fences / extra text)
        parsed = _extract_json(resp.text)
        if not parsed:
            # Fall back: pick label by substring match
            lower = resp.text.lower()
            for lbl in labels:
                if lbl.lower() in lower:
                    return {
                        "category": lbl,
                        "confidence": 0.5,
                        "reasoning": "fallback substring match",
                        "raw": resp.text,
                    }
            return {
                "category": labels[-1],
                "confidence": 0.0,
                "reasoning": "could not parse classification",
                "raw": resp.text,
            }

        cat = str(parsed.get("category", "")).strip()
        # Normalize to a known label (case-insensitive)
        for lbl in labels:
            if lbl.lower() == cat.lower():
                cat = lbl
                break
        return {
            "category": cat or labels[-1],
            "confidence": float(parsed.get("confidence", 0.0) or 0.0),
            "reasoning": str(parsed.get("reasoning", "")),
            "raw": resp.text,
            "provider": provider.name,
        }


def _extract_json(text: str) -> dict[str, Any] | None:
    import json
    import re

    if not text:
        return None
    # Try direct
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try fenced
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Try first {...} block
    m = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None
