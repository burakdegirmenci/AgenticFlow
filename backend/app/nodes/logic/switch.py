"""Switch (multi-branch) node - routes flow by a field's value."""

from typing import Any

from app.engine.context import ExecutionContext
from app.engine.node_base import BaseNode
from app.nodes import register
from app.nodes.transform.filter import _get_field
from app.nodes.transform.parse_stok import _resolve_items


@register
class SwitchNode(BaseNode):
    type_id = "logic.switch"
    category = "logic"
    display_name = "Switch (Çoklu Dal)"
    description = "Bir alanın değerine göre akışı birden fazla dala yönlendirir."
    icon = "git-merge"
    color = "#f59e0b"

    output_schema = {
        "type": "object",
        "properties": {
            "_branches": {"type": "array"},
            "value": {"type": "string"},
        },
    }

    config_schema = {
        "type": "object",
        "properties": {
            "field": {
                "type": "string",
                "title": "Alan",
                "description": "Gruplama yapılacak alan adı (dotted path destekli)",
                "default": "",
            },
            "default_branch": {
                "type": "string",
                "title": "Varsayılan Dal",
                "description": "Hiçbir case eşleşmediğinde gidilecek sourceHandle",
                "default": "default",
            },
            "input_key": {
                "type": "string",
                "title": "Giriş Anahtarı",
                "default": "",
            },
        },
        "required": ["field"],
    }

    async def execute(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        field = str(config.get("field", ""))
        default_branch = str(config.get("default_branch", "default"))
        input_key = config.get("input_key", "") or ""

        items = _resolve_items(inputs, input_key)
        if not items:
            value = ""
        else:
            first = items[0]
            raw = _get_field(first, field) if field else first
            value = str(raw) if raw is not None else ""

        # The matched branch is the value itself; the executor compares edge
        # sourceHandle with this value. If no edge matches, default_branch
        # is used (executor falls back to default if present).
        return {
            "_branches": [value or default_branch, default_branch],
            "value": value,
        }
