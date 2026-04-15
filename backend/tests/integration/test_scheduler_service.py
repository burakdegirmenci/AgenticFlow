"""SchedulerService — lifecycle, job registration, trigger builder.

``AsyncIOScheduler`` requires a running asyncio event loop at ``start()``
time. Because ``pytest-asyncio`` is configured in ``asyncio_mode = "auto"``,
every ``async def`` test here runs inside the event loop automatically.

We use an isolated ``SchedulerService`` instance per test (not the module
singleton) to avoid cross-test contamination of registered jobs. The
scheduler's internal ``SessionLocal`` is monkeypatched so its DB work
hits the in-memory test session.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from app.services import scheduler_service as scheduler_module
from app.services.scheduler_service import SchedulerService

pytestmark = pytest.mark.integration


@pytest.fixture
async def svc() -> AsyncIterator[SchedulerService]:
    """A started SchedulerService instance, torn down after the test."""
    scheduler = SchedulerService()
    scheduler.start()
    try:
        yield scheduler
    finally:
        scheduler.shutdown()


@pytest.fixture
def patched_session_factory(db_session, monkeypatch):
    """Point scheduler_service.SessionLocal at the test session.

    Also neutralises the session's ``close()`` so the scheduler's
    ``finally: db.close()`` blocks don't detach our test fixtures.
    """
    monkeypatch.setattr(scheduler_module, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)


def _schedule_graph(cron: str, node_id: str = "trigger") -> dict:
    return {
        "nodes": [
            {
                "id": node_id,
                "type": "trigger.schedule",
                "position": {"x": 0, "y": 0},
                "data": {"config": {"cron": cron, "timezone": "UTC"}},
            }
        ],
        "edges": [],
    }


def _polling_graph(interval: int, node_id: str = "poll") -> dict:
    return {
        "nodes": [
            {
                "id": node_id,
                "type": "trigger.polling",
                "position": {"x": 0, "y": 0},
                "data": {"config": {"interval_seconds": interval}},
            }
        ],
        "edges": [],
    }


# ---------------------------------------------------------------------------
# Lifecycle — these don't need a running event loop for start/shutdown
# when we check the plain state fields only.
# ---------------------------------------------------------------------------
class TestLifecycle:
    async def test_start_is_idempotent(self) -> None:
        scheduler = SchedulerService()
        assert not scheduler.is_started()
        scheduler.start()
        try:
            assert scheduler.is_started()
            scheduler.start()  # second call — must not raise
            assert scheduler.is_started()
        finally:
            scheduler.shutdown()
        assert not scheduler.is_started()

    def test_shutdown_without_start_is_safe(self) -> None:
        scheduler = SchedulerService()
        scheduler.shutdown()
        assert not scheduler.is_started()

    def test_operations_on_unstarted_service_are_noops(self) -> None:
        scheduler = SchedulerService()
        assert scheduler.list_jobs() == []
        assert scheduler.register_workflow(1) == 0
        assert scheduler.unregister_workflow(1) == 0


# ---------------------------------------------------------------------------
# Trigger-builder — the pure mapping from node config → APScheduler trigger.
# ---------------------------------------------------------------------------
class TestBuildTrigger:
    async def test_cron_is_accepted(self, svc: SchedulerService) -> None:
        trigger = svc._build_trigger(
            "trigger.schedule", {"cron": "0 6 * * *", "timezone": "Europe/Istanbul"}
        )
        assert trigger is not None
        assert trigger.__class__.__name__ == "CronTrigger"

    async def test_cron_with_empty_expression_returns_none(self, svc: SchedulerService) -> None:
        assert svc._build_trigger("trigger.schedule", {"cron": ""}) is None

    async def test_cron_with_invalid_expression_returns_none(self, svc: SchedulerService) -> None:
        assert svc._build_trigger("trigger.schedule", {"cron": "not a cron"}) is None

    async def test_polling_uses_interval_trigger(self, svc: SchedulerService) -> None:
        trigger = svc._build_trigger("trigger.polling", {"interval_seconds": 60})
        assert trigger is not None
        assert trigger.__class__.__name__ == "IntervalTrigger"

    async def test_polling_floor_interval_at_10_seconds(self, svc: SchedulerService) -> None:
        """Under-10s polling would hammer Ticimax; service forces a floor."""
        trigger = svc._build_trigger("trigger.polling", {"interval_seconds": 2})
        assert trigger is not None
        assert trigger.__class__.__name__ == "IntervalTrigger"

    async def test_polling_non_numeric_returns_none(self, svc: SchedulerService) -> None:
        assert svc._build_trigger("trigger.polling", {"interval_seconds": "not-a-number"}) is None

    async def test_unknown_node_type_returns_none(self, svc: SchedulerService) -> None:
        assert svc._build_trigger("ticimax.urun.select", {}) is None


# ---------------------------------------------------------------------------
# Registration against a real Workflow row.
# ---------------------------------------------------------------------------
class TestRegister:
    async def test_register_schedule_workflow(
        self, svc, workflow_factory, patched_session_factory
    ) -> None:
        wf = workflow_factory(is_active=True, graph=_schedule_graph("*/15 * * * *"))
        added = svc.register_workflow(wf.id)
        assert added == 1

        jobs = svc.list_jobs()
        assert len(jobs) == 1
        assert jobs[0]["id"].startswith(f"wf{wf.id}:")

    async def test_register_polling_workflow(
        self, svc, workflow_factory, patched_session_factory
    ) -> None:
        wf = workflow_factory(is_active=True, graph=_polling_graph(interval=60))
        assert svc.register_workflow(wf.id) == 1

    async def test_inactive_workflow_registers_nothing(
        self, svc, workflow_factory, patched_session_factory
    ) -> None:
        wf = workflow_factory(is_active=False, graph=_schedule_graph("0 * * * *"))
        assert svc.register_workflow(wf.id) == 0
        assert svc.list_jobs() == []

    async def test_missing_workflow_is_safe(self, svc, patched_session_factory) -> None:
        assert svc.register_workflow(9999) == 0

    async def test_register_is_idempotent(
        self, svc, workflow_factory, patched_session_factory
    ) -> None:
        wf = workflow_factory(is_active=True, graph=_schedule_graph("0 6 * * *"))
        svc.register_workflow(wf.id)
        svc.register_workflow(wf.id)  # second call replaces
        assert len(svc.list_jobs()) == 1

    async def test_multiple_trigger_nodes_in_one_workflow(
        self, svc, workflow_factory, patched_session_factory
    ) -> None:
        wf = workflow_factory(
            is_active=True,
            graph={
                "nodes": [
                    {
                        "id": "cron",
                        "type": "trigger.schedule",
                        "position": {"x": 0, "y": 0},
                        "data": {"config": {"cron": "0 6 * * *"}},
                    },
                    {
                        "id": "poll",
                        "type": "trigger.polling",
                        "position": {"x": 0, "y": 100},
                        "data": {"config": {"interval_seconds": 30}},
                    },
                ],
                "edges": [],
            },
        )
        added = svc.register_workflow(wf.id)
        assert added == 2
        ids = {job["id"] for job in svc.list_jobs()}
        assert ids == {f"wf{wf.id}:cron", f"wf{wf.id}:poll"}

    async def test_unregister_removes_all_jobs_for_workflow(
        self, svc, workflow_factory, patched_session_factory
    ) -> None:
        wf = workflow_factory(is_active=True, graph=_schedule_graph("0 6 * * *"))
        svc.register_workflow(wf.id)
        assert svc.list_jobs() != []
        removed = svc.unregister_workflow(wf.id)
        assert removed == 1
        assert svc.list_jobs() == []

    async def test_unregister_other_workflows_untouched(
        self, svc, workflow_factory, patched_session_factory
    ) -> None:
        wf_a = workflow_factory(is_active=True, graph=_schedule_graph("0 6 * * *"))
        wf_b = workflow_factory(is_active=True, graph=_schedule_graph("0 7 * * *"))
        svc.register_workflow(wf_a.id)
        svc.register_workflow(wf_b.id)
        assert len(svc.list_jobs()) == 2
        svc.unregister_workflow(wf_a.id)
        assert len(svc.list_jobs()) == 1
        assert svc.list_jobs()[0]["id"].startswith(f"wf{wf_b.id}:")


# ---------------------------------------------------------------------------
# refresh_all — used at startup to reinstate every active workflow.
# ---------------------------------------------------------------------------
class TestRefreshAll:
    async def test_refresh_all_picks_up_every_active_workflow(
        self, svc, workflow_factory, patched_session_factory
    ) -> None:
        wf_a = workflow_factory(is_active=True, graph=_schedule_graph("0 6 * * *"))
        wf_b = workflow_factory(is_active=True, graph=_polling_graph(45))
        workflow_factory(is_active=False, graph=_schedule_graph("0 7 * * *"))

        svc.refresh_all()

        ids = {job["id"] for job in svc.list_jobs()}
        assert any(i.startswith(f"wf{wf_a.id}:") for i in ids)
        assert any(i.startswith(f"wf{wf_b.id}:") for i in ids)
        assert len(ids) == 2

    async def test_refresh_all_is_idempotent(
        self, svc, workflow_factory, patched_session_factory
    ) -> None:
        wf = workflow_factory(is_active=True, graph=_schedule_graph("0 6 * * *"))
        svc.refresh_all()
        svc.refresh_all()
        assert len(svc.list_jobs()) == 1
        assert svc.list_jobs()[0]["id"].startswith(f"wf{wf.id}:")
