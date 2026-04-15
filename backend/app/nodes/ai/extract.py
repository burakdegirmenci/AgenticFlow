"""AI extract node - structured data extraction from free-form text."""

from typing import Any

from app.engine.context import ExecutionContext
from app.engine.errors import NodeError
from app.engine.node_base import BaseNode
from app.nodes import register
from app.nodes.ai._common import flatten_inputs, render_template
from app.services.llm import LLMProviderError, get_provider
from app.services.llm.base import LLMMessage


@register
class AIExtractNode(BaseNode):
    type_id = "ai.extract"
    category = "ai"
    display_name = "AI Veri Çıkar"
    description = (
        "Serbest metinden yapılandırılmış veri çıkarır. "
        "Fatura, adres, sipariş gibi bilgileri JSON'a dönüştürür."
    )
    icon = "file-text"
    color = "#2563EB"

    input_schema = {"type": "object"}

    output_schema = {
        "type": "object",
        "properties": {
            "data": {"type": "object"},
            "raw": {"type": "string"},
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
                "title": "Kaynak Metin",
                "description": "{{field}} ile input'tan değer al",
                "default": "{{text}}",
            },
            "fields": {
                "type": "string",
                "title": "Alanlar",
                "description": (
                    "Virgülle ayrılmış alan listesi (örn: "
                    "ad:string, telefon:string, tutar:number, tarih:string)"
                ),
                "default": "",
            },
            "instructions": {
                "type": "string",
                "title": "Ek Talimat",
                "default": "",
            },
        },
        "required": ["fields"],
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

        fields_raw = str(config.get("fields", ""))
        fields = _parse_fields(fields_raw)
        if not fields:
            raise NodeError("", self.type_id, "fields is required")

        merged = flatten_inputs(inputs)
        text = render_template(str(config.get("text_template", "{{text}}")), merged)
        instructions = str(config.get("instructions", "")).strip()

        field_desc = "\n".join(f"- {name}: {ftype}" for name, ftype in fields)
        example_obj = {name: _example_for(ftype) for name, ftype in fields}
        import json as _json

        system = (
            "Sen bir yapılandırılmış veri çıkarma uzmanısın. Verilen metinden "
            "aşağıdaki alanları çıkar ve SADECE JSON döndür.\n\n"
            "Alanlar:\n"
            f"{field_desc}\n\n"
            "Örnek çıktı formatı:\n"
            f"{_json.dumps(example_obj, ensure_ascii=False)}\n\n"
            "Bir alan metinde yoksa null yaz. Sadece JSON döndür."
        )
        if instructions:
            system += "\n\nEk talimat: " + instructions

        try:
            resp = await provider.complete(
                system=system,
                messages=[LLMMessage(role="user", content=text)],
                model=(config.get("model") or None),
                temperature=0.0,
                max_tokens=2048,
            )
        except LLMProviderError as e:
            raise NodeError("", self.type_id, str(e))

        from app.nodes.ai.classify import _extract_json

        data = _extract_json(resp.text) or {}
        return {
            "data": data,
            "raw": resp.text,
            "provider": provider.name,
        }


def _parse_fields(raw: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" in item:
            name, ftype = item.split(":", 1)
            out.append((name.strip(), ftype.strip().lower() or "string"))
        else:
            out.append((item, "string"))
    return out


def _example_for(ftype: str) -> Any:
    ftype = ftype.lower()
    if ftype in ("number", "int", "integer", "float"):
        return 0
    if ftype in ("bool", "boolean"):
        return False
    if ftype in ("array", "list"):
        return []
    if ftype in ("object", "dict"):
        return {}
    return "..."
