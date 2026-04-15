"""Filter transform node - keep items matching a condition expression."""
from typing import Any

from app.engine.context import ExecutionContext
from app.engine.node_base import BaseNode
from app.nodes import register
from app.nodes.transform.parse_stok import _resolve_items


def _get_field(item: Any, field: str) -> Any:
    if isinstance(item, dict):
        # Support dotted paths: "Kargo.Firma"
        parts = field.split(".")
        cur: Any = item
        for p in parts:
            if isinstance(cur, dict) and p in cur:
                cur = cur[p]
            else:
                return None
        return cur
    return None


def _compare(left: Any, op: str, right: Any) -> bool:
    try:
        if op == "eq":
            return left == right
        if op == "ne":
            return left != right
        if op == "gt":
            return float(left) > float(right)
        if op == "lt":
            return float(left) < float(right)
        if op == "gte":
            return float(left) >= float(right)
        if op == "lte":
            return float(left) <= float(right)
        if op == "contains":
            return str(right) in str(left)
        if op == "not_contains":
            return str(right) not in str(left)
        if op == "empty":
            return left in (None, "", [], {})
        if op == "not_empty":
            return left not in (None, "", [], {})
        if op == "length_lt":
            # String length strictly less than right (numeric).
            # None is treated as length 0 so truly empty fields match.
            if left is None:
                return 0 < int(float(right))
            return len(str(left)) < int(float(right))
        if op == "length_gt":
            if left is None:
                return False
            return len(str(left)) > int(float(right))
        if op == "in":
            parts = [p.strip() for p in str(right).split(",")]
            return str(left) in parts
    except Exception:
        return False
    return False


@register
class FilterNode(BaseNode):
    type_id = "transform.filter"
    category = "transform"
    display_name = "Filtrele"
    description = "Bir koşula uyan öğeleri tutar, diğerlerini atar."
    icon = "filter"
    color = "#8b5cf6"

    input_schema = {
        "type": "object",
        "properties": {"items": {"type": "array"}},
    }

    output_schema = {
        "type": "object",
        "properties": {
            "items": {"type": "array"},
            "count": {"type": "integer"},
            "removed": {"type": "integer"},
        },
    }

    config_schema = {
        "type": "object",
        "properties": {
            "field": {
                "type": "string",
                "title": "Alan",
                "description": "Kontrol edilecek alan adı (dotted path destekli)",
                "default": "",
            },
            "op": {
                "type": "string",
                "title": "Operatör",
                "default": "eq",
                "enum": [
                    "eq",
                    "ne",
                    "gt",
                    "lt",
                    "gte",
                    "lte",
                    "contains",
                    "not_contains",
                    "empty",
                    "not_empty",
                    "length_lt",
                    "length_gt",
                    "in",
                ],
            },
            "value": {
                "type": "string",
                "title": "Değer",
                "description": "Karşılaştırma değeri (empty/not_empty için boş bırak)",
                "default": "",
            },
            "input_key": {
                "type": "string",
                "title": "Giriş Anahtarı",
                "default": "",
            },
        },
        "required": ["field", "op"],
    }

    async def execute(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        field = str(config.get("field", ""))
        op = str(config.get("op", "eq"))
        value = config.get("value", "")
        input_key = config.get("input_key", "") or ""

        items = _resolve_items(inputs, input_key)

        kept: list[Any] = []
        for item in items:
            left = _get_field(item, field) if field else item
            if _compare(left, op, value):
                kept.append(item)

        return {
            "items": kept,
            "count": len(kept),
            "removed": len(items) - len(kept),
        }
