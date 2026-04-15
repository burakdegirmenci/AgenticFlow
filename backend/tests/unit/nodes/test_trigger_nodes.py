"""triggers/manual, schedule, polling — entry points that emit start metadata."""

from __future__ import annotations

from app.nodes.triggers.manual import ManualTriggerNode
from app.nodes.triggers.polling import PollingTriggerNode
from app.nodes.triggers.schedule import ScheduleTriggerNode


async def test_manual_trigger_surfaces_context_trigger_input(execution_context) -> None:
    execution_context.trigger_input = {"reason": "user clicked run"}
    node = ManualTriggerNode()
    out = await node.execute(execution_context, {}, {})
    assert out["input"] == {"reason": "user clicked run"}
    assert "triggered_at" in out


async def test_manual_trigger_with_empty_context(execution_context) -> None:
    node = ManualTriggerNode()
    out = await node.execute(execution_context, {}, {})
    assert out["input"] == {}


async def test_schedule_trigger_returns_cron_and_timezone(execution_context) -> None:
    node = ScheduleTriggerNode()
    out = await node.execute(
        execution_context, {}, {"cron": "0 6 * * *", "timezone": "Europe/Istanbul"}
    )
    assert out["cron"] == "0 6 * * *"
    assert out["timezone"] == "Europe/Istanbul"
    assert "triggered_at" in out


async def test_schedule_trigger_uses_defaults_when_config_empty(execution_context) -> None:
    node = ScheduleTriggerNode()
    out = await node.execute(execution_context, {}, {})
    assert out["cron"] == ""
    assert out["timezone"] == "UTC"


async def test_polling_trigger_returns_interval(execution_context) -> None:
    node = PollingTriggerNode()
    out = await node.execute(execution_context, {}, {"interval_seconds": 60})
    assert out["interval_seconds"] == 60
    assert "triggered_at" in out


async def test_polling_trigger_defaults_to_300(execution_context) -> None:
    node = PollingTriggerNode()
    out = await node.execute(execution_context, {}, {})
    assert out["interval_seconds"] == 300


async def test_polling_trigger_coerces_string_interval(execution_context) -> None:
    """Config round-trip through JSON might deliver the int as a string."""
    node = PollingTriggerNode()
    out = await node.execute(execution_context, {}, {"interval_seconds": "45"})
    assert out["interval_seconds"] == 45
