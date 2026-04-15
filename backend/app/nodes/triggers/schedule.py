"""Schedule trigger - cron-based automatic workflow execution.

The node itself is a pure marker: its ``execute()`` simply echoes the cron
expression and the trigger time. The actual scheduling happens in
``SchedulerService`` which reads the config at workflow activation time and
registers an APScheduler ``CronTrigger`` job.
"""

from typing import Any

from app.engine.context import ExecutionContext
from app.engine.node_base import BaseNode
from app.nodes import register
from app.utils.time import utcnow


@register
class ScheduleTriggerNode(BaseNode):
    type_id = "trigger.schedule"
    category = "trigger"
    display_name = "Zamanlanmış"
    description = "Cron ifadesine göre workflow'u otomatik tetikler."
    icon = "clock"
    color = "#2563EB"

    output_schema = {
        "type": "object",
        "properties": {
            "triggered_at": {"type": "string", "format": "date-time"},
            "cron": {"type": "string"},
        },
    }

    config_schema = {
        "type": "object",
        "properties": {
            "cron": {
                "type": "string",
                "title": "Cron İfadesi",
                "description": "5 parçalı: dakika saat gün ay hafta_günü (örn: '*/5 * * * *' her 5 dk)",
                "default": "0 * * * *",
            },
            "timezone": {
                "type": "string",
                "title": "Saat Dilimi",
                "description": (
                    "IANA timezone adı. Boş bırakılırsa UTC. Türkiye için: 'Europe/Istanbul'."
                ),
                "default": "Europe/Istanbul",
            },
        },
        "required": ["cron"],
    }

    async def execute(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "triggered_at": utcnow().isoformat(),
            "cron": config.get("cron", ""),
            "timezone": config.get("timezone", "UTC"),
        }
