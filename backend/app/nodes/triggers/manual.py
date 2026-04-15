"""Manual trigger - workflow starts here when user clicks Run."""

from typing import Any

from app.engine.context import ExecutionContext
from app.engine.node_base import BaseNode
from app.nodes import register


@register
class ManualTriggerNode(BaseNode):
    type_id = "trigger.manual"
    category = "trigger"
    display_name = "Manuel Başlat"
    description = "Workflow'u manuel olarak çalıştır. Run butonu ile tetiklenir."
    icon = "play"
    color = "#2563EB"

    output_schema = {
        "type": "object",
        "properties": {
            "triggered_at": {"type": "string", "format": "date-time"},
            "input": {"type": "object"},
        },
    }

    config_schema = {"type": "object", "properties": {}}

    async def execute(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        from datetime import datetime

        return {
            "triggered_at": datetime.utcnow().isoformat(),
            "input": context.trigger_input,
        }
