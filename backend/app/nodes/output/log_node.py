"""Log node - writes inputs to execution log (for debugging)."""
from typing import Any

from app.engine.context import ExecutionContext
from app.engine.node_base import BaseNode
from app.nodes import register


@register
class LogNode(BaseNode):
    type_id = "output.log"
    category = "output"
    display_name = "Log"
    description = "Gelen veriyi execution log'una yazar. Debug için."
    icon = "file-text"
    color = "#6b7280"

    config_schema = {
        "type": "object",
        "properties": {
            "label": {
                "type": "string",
                "title": "Etiket",
                "default": "log",
            },
            "max_length": {
                "type": "integer",
                "title": "Maksimum Uzunluk",
                "default": 5000,
            },
        },
    }

    async def execute(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        import json
        label = config.get("label", "log")
        max_length = int(config.get("max_length", 5000))
        try:
            payload = json.dumps(inputs, default=str, ensure_ascii=False)
        except Exception:
            payload = str(inputs)
        if len(payload) > max_length:
            payload = payload[:max_length] + "...[truncated]"
        return {"label": label, "logged": payload, "input_count": len(inputs)}
