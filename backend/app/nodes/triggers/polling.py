"""Polling trigger - interval-based automatic workflow execution.

Like ``trigger.schedule`` but expressed as "every N seconds" (interval) rather
than a cron expression. Intended for scenarios where you want to repeatedly
query Ticimax for new items and then diff with ``transform.only_new``.

Combine with a downstream Ticimax query node + ``transform.only_new`` to build
a "watch for new orders" flow.
"""
from datetime import datetime
from typing import Any

from app.engine.context import ExecutionContext
from app.engine.node_base import BaseNode
from app.nodes import register


@register
class PollingTriggerNode(BaseNode):
    type_id = "trigger.polling"
    category = "trigger"
    display_name = "Polling"
    description = "Periyodik (interval) tetikleyici. Sıklıkla yeni kayıt izlemek için."
    icon = "repeat"
    color = "#2563EB"

    output_schema = {
        "type": "object",
        "properties": {
            "triggered_at": {"type": "string", "format": "date-time"},
            "interval_seconds": {"type": "integer"},
        },
    }

    config_schema = {
        "type": "object",
        "properties": {
            "interval_seconds": {
                "type": "integer",
                "title": "Aralık (saniye)",
                "description": "En az 10 saniye. Ticimax rate limit'ine dikkat.",
                "default": 300,
                "minimum": 10,
            },
        },
        "required": ["interval_seconds"],
    }

    async def execute(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "triggered_at": datetime.utcnow().isoformat(),
            "interval_seconds": int(config.get("interval_seconds", 300)),
        }
