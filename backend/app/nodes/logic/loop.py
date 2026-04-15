"""Loop (ForEach) node - iterate over a list and collect outputs.

MVP behavior: Loop node marks each item as `current_item` in context and
emits an output containing the list. Downstream subgraph execution (parallel
per-item) is Faz 3+. For now, this node passes through the list and provides
a `count` so following transform nodes can operate on the whole batch.
"""

from typing import Any

from app.engine.context import ExecutionContext
from app.engine.node_base import BaseNode
from app.nodes import register
from app.nodes.transform.parse_stok import _resolve_items


@register
class LoopNode(BaseNode):
    type_id = "logic.loop"
    category = "logic"
    display_name = "Döngü (ForEach)"
    description = "Bir dizi üzerinde dön. MVP: batch pass-through, Faz 3'te per-item subgraph."
    icon = "repeat"
    color = "#f59e0b"

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
            "input_key": {
                "type": "string",
                "title": "Giriş Anahtarı",
                "default": "",
            },
            "limit": {
                "type": "integer",
                "title": "Maks. Öğe Sayısı",
                "description": "0 = hepsi",
                "default": 0,
                "minimum": 0,
            },
        },
    }

    async def execute(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        input_key = config.get("input_key", "") or ""
        limit = int(config.get("limit", 0))

        items = _resolve_items(inputs, input_key)
        if limit > 0:
            items = items[:limit]

        return {"items": items, "count": len(items)}
