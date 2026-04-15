"""Map transform node - rename, pick, or add fields on each item."""

from typing import Any

from app.engine.context import ExecutionContext
from app.engine.node_base import BaseNode
from app.nodes import register
from app.nodes.transform.filter import _get_field
from app.nodes.transform.parse_stok import _resolve_items


@register
class MapNode(BaseNode):
    type_id = "transform.map"
    category = "transform"
    display_name = "Map (Alan Dönüştür)"
    description = "Her öğe için alanları seçer, yeniden adlandırır veya sabit değer ekler."
    icon = "shuffle"
    color = "#8b5cf6"

    input_schema = {"type": "object", "properties": {"items": {"type": "array"}}}
    output_schema = {
        "type": "object",
        "properties": {
            "items": {"type": "array"},
            "count": {"type": "integer"},
        },
    }

    config_schema = {
        "type": "object",
        "properties": {
            "mappings": {
                "type": "object",
                "title": "Alan Eşlemeleri",
                "description": (
                    'JSON object: {"yeni_alan": "=eski.alan"} veya '
                    '{"sabit": "\'deger\'"}. "=prefix" ile source path, '
                    "aksi halde literal string."
                ),
                "default": {},
            },
            "keep_original": {
                "type": "boolean",
                "title": "Orijinal Alanları Koru",
                "default": False,
            },
            "input_key": {
                "type": "string",
                "title": "Giriş Anahtarı",
                "default": "",
            },
        },
    }

    async def execute(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        mappings = config.get("mappings") or {}
        if isinstance(mappings, str):
            # allow raw JSON string from UI
            import json

            try:
                mappings = json.loads(mappings)
            except Exception:
                mappings = {}
        keep_original = bool(config.get("keep_original", False))
        input_key = config.get("input_key", "") or ""

        items = _resolve_items(inputs, input_key)
        out_items: list[Any] = []

        for item in items:
            if not isinstance(item, dict):
                out_items.append(item)
                continue
            new_item: dict[str, Any] = dict(item) if keep_original else {}
            for target, expr in mappings.items():
                if isinstance(expr, str) and expr.startswith("="):
                    new_item[target] = _get_field(item, expr[1:])
                else:
                    new_item[target] = expr
            out_items.append(new_item)

        return {"items": out_items, "count": len(out_items)}
