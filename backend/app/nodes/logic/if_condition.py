"""If (conditional branch) node - routes flow along true/false edges."""
from typing import Any

from app.engine.context import ExecutionContext
from app.engine.node_base import BaseNode
from app.nodes import register
from app.nodes.transform.filter import _compare, _get_field
from app.nodes.transform.parse_stok import _resolve_items


@register
class IfConditionNode(BaseNode):
    type_id = "logic.if"
    category = "logic"
    display_name = "Eğer (If)"
    description = "Bir koşulu değerlendirir, akışı 'true' veya 'false' dalına yönlendirir."
    icon = "git-branch"
    color = "#f59e0b"

    output_schema = {
        "type": "object",
        "properties": {
            "_branches": {"type": "array"},
            "value": {"type": "boolean"},
        },
    }

    config_schema = {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "title": "Mod",
                "description": "item: ilk öğeyi kontrol et | list_empty: dizi boş mu",
                "default": "item",
                "enum": ["item", "list_empty", "list_not_empty"],
            },
            "field": {
                "type": "string",
                "title": "Alan",
                "description": "item modunda kontrol edilecek alan",
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
                    "in",
                ],
            },
            "value": {
                "type": "string",
                "title": "Değer",
                "default": "",
            },
            "input_key": {
                "type": "string",
                "title": "Giriş Anahtarı",
                "default": "",
            },
        },
        "required": ["mode"],
    }

    async def execute(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        mode = str(config.get("mode", "item"))
        input_key = config.get("input_key", "") or ""
        items = _resolve_items(inputs, input_key)

        if mode == "list_empty":
            result = len(items) == 0
        elif mode == "list_not_empty":
            result = len(items) > 0
        else:
            field = str(config.get("field", ""))
            op = str(config.get("op", "eq"))
            value = config.get("value", "")
            if not items:
                result = False
            else:
                first = items[0]
                left = _get_field(first, field) if field else first
                result = _compare(left, op, value)

        branch = "true" if result else "false"
        # Pass the resolved items through so downstream nodes (filter,
        # vision_batch, etc.) can still find them via the standard
        # _resolve_items walk. Keys are ordered so the items list comes
        # before any underscore-prefixed routing marker.
        return {
            "items": items,
            "count": len(items),
            "value": result,
            "_branches": [branch],
        }
