"""Aggregate transform node - count / sum / group_by."""
from typing import Any

from app.engine.context import ExecutionContext
from app.engine.node_base import BaseNode
from app.nodes import register
from app.nodes.transform.parse_stok import _resolve_items
from app.nodes.transform.filter import _get_field


@register
class AggregateNode(BaseNode):
    type_id = "transform.aggregate"
    category = "transform"
    display_name = "Aggregate (Topla/Grupla)"
    description = "Öğeleri sayar, toplar veya alana göre gruplar."
    icon = "bar-chart-2"
    color = "#8b5cf6"

    input_schema = {"type": "object", "properties": {"items": {"type": "array"}}}

    output_schema = {
        "type": "object",
        "properties": {
            "result": {"type": "object"},
        },
    }

    config_schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "title": "İşlem",
                "default": "count",
                "enum": ["count", "sum", "avg", "min", "max", "group_by"],
            },
            "field": {
                "type": "string",
                "title": "Alan",
                "description": "sum/avg/min/max için sayısal alan; group_by için gruplama alanı",
                "default": "",
            },
            "input_key": {
                "type": "string",
                "title": "Giriş Anahtarı",
                "default": "",
            },
        },
        "required": ["operation"],
    }

    async def execute(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        op = str(config.get("operation", "count"))
        field = str(config.get("field", ""))
        input_key = config.get("input_key", "") or ""

        items = _resolve_items(inputs, input_key)

        if op == "count":
            return {"result": {"count": len(items)}}

        if op == "group_by":
            groups: dict[str, list[Any]] = {}
            for item in items:
                key = str(_get_field(item, field) if field else "_")
                groups.setdefault(key, []).append(item)
            return {
                "result": {
                    "groups": {k: {"count": len(v), "items": v} for k, v in groups.items()},
                    "group_count": len(groups),
                }
            }

        # numeric aggregations
        values: list[float] = []
        for item in items:
            v = _get_field(item, field) if field else None
            if v is None:
                continue
            try:
                values.append(float(v))
            except (TypeError, ValueError):
                continue

        if not values:
            return {"result": {op: None, "count": 0}}

        if op == "sum":
            out = sum(values)
        elif op == "avg":
            out = sum(values) / len(values)
        elif op == "min":
            out = min(values)
        elif op == "max":
            out = max(values)
        else:
            out = None

        return {"result": {op: out, "count": len(values)}}
