"""APScheduler integration for cron & polling triggers.

Responsibilities
----------------
- Own a single ``AsyncIOScheduler`` instance tied to the FastAPI event loop.
- On startup, scan every ``is_active`` workflow and register its schedule /
  polling trigger nodes as APScheduler jobs.
- On workflow activate / deactivate / graph update, add or remove jobs
  idempotently via ``register_workflow`` / ``unregister_workflow``.
- Each job, when fired, opens a fresh DB session, loads the workflow, and
  runs ``WorkflowExecutor`` with the appropriate trigger type.

Job ID convention
-----------------
``wf{workflow_id}:{node_id}`` — unique per (workflow, trigger node). This
allows multiple trigger nodes inside the same workflow (e.g. a polling node
AND a schedule node) and makes removal simple.
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.database import SessionLocal
from app.engine.executor import WorkflowExecutor
from app.models.execution import TriggerType
from app.models.workflow import Workflow

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


_SCHEDULE_NODE_TYPE = "trigger.schedule"
_POLLING_NODE_TYPE = "trigger.polling"


def _job_id(workflow_id: int, node_id: str) -> str:
    return f"wf{workflow_id}:{node_id}"


class SchedulerService:
    """Singleton wrapper around a single AsyncIOScheduler instance."""

    def __init__(self) -> None:
        self._scheduler: AsyncIOScheduler | None = None
        self._started: bool = False

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> None:
        if self._started:
            return
        self._scheduler = AsyncIOScheduler(timezone="UTC")
        self._scheduler.start()
        self._started = True
        logger.info("SchedulerService started")

    def shutdown(self) -> None:
        if not self._started or self._scheduler is None:
            return
        try:
            self._scheduler.shutdown(wait=False)
        except Exception:  # noqa: BLE001
            logger.exception("SchedulerService shutdown failed")
        self._started = False
        self._scheduler = None
        logger.info("SchedulerService stopped")

    def refresh_all(self) -> None:
        """Scan active workflows and (re-)register all their trigger jobs.

        Called once at startup after ``start()``. Safe to call again; it will
        remove all existing jobs and re-add them based on the current DB state.
        """
        if not self._started or self._scheduler is None:
            return
        # Wipe existing jobs first so we never leave stale ones behind.
        self._scheduler.remove_all_jobs()

        db = SessionLocal()
        try:
            workflows = (
                db.query(Workflow).filter(Workflow.is_active.is_(True)).all()
            )
            for wf in workflows:
                self._register_workflow_jobs(wf)
            logger.info(
                "SchedulerService refresh: registered jobs for %d active workflows",
                len(workflows),
            )
        finally:
            db.close()

    # ------------------------------------------------------------------ register
    def register_workflow(self, workflow_id: int) -> int:
        """Register (or re-register) all schedule/polling jobs for a workflow.

        Returns the number of jobs added. Silently no-ops if the workflow is
        inactive or the scheduler isn't running.
        """
        if not self._started or self._scheduler is None:
            return 0
        # Always clear existing first - idempotent re-registration.
        self.unregister_workflow(workflow_id)

        db = SessionLocal()
        try:
            wf = db.query(Workflow).filter(Workflow.id == workflow_id).one_or_none()
            if wf is None or not wf.is_active:
                return 0
            return self._register_workflow_jobs(wf)
        finally:
            db.close()

    def unregister_workflow(self, workflow_id: int) -> int:
        """Remove every job belonging to a workflow. Returns removed count."""
        if not self._started or self._scheduler is None:
            return 0
        prefix = f"wf{workflow_id}:"
        removed = 0
        for job in list(self._scheduler.get_jobs()):
            if job.id.startswith(prefix):
                try:
                    self._scheduler.remove_job(job.id)
                    removed += 1
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to remove job %s", job.id)
        if removed:
            logger.info(
                "Removed %d scheduled job(s) for workflow %d", removed, workflow_id
            )
        return removed

    def list_jobs(self) -> list[dict]:
        """Debug helper: list currently-scheduled jobs as plain dicts."""
        if not self._started or self._scheduler is None:
            return []
        out: list[dict] = []
        for job in self._scheduler.get_jobs():
            out.append(
                {
                    "id": job.id,
                    "next_run_time": (
                        job.next_run_time.isoformat() if job.next_run_time else None
                    ),
                    "trigger": str(job.trigger),
                }
            )
        return out

    # ------------------------------------------------------------------ internal
    def _register_workflow_jobs(self, wf: Workflow) -> int:
        """Scan a workflow's graph and register APScheduler jobs for triggers."""
        assert self._scheduler is not None
        graph = wf.graph_json or {}
        nodes = graph.get("nodes", []) or []
        count = 0
        for node in nodes:
            node_type = node.get("type")
            node_id = node.get("id")
            config = (node.get("data") or {}).get("config") or {}
            if not node_id or not node_type:
                continue
            trigger = self._build_trigger(node_type, config)
            if trigger is None:
                continue
            try:
                self._scheduler.add_job(
                    _run_workflow_job,
                    trigger=trigger,
                    id=_job_id(wf.id, node_id),
                    args=[wf.id, node_type, node_id],
                    replace_existing=True,
                    max_instances=1,
                    coalesce=True,
                    misfire_grace_time=60,
                )
                count += 1
                logger.info(
                    "Scheduled job for workflow %d node %s (%s)",
                    wf.id,
                    node_id,
                    node_type,
                )
            except Exception as e:  # noqa: BLE001
                logger.error(
                    "Failed to schedule workflow %d node %s: %s",
                    wf.id,
                    node_id,
                    e,
                )
        return count

    def _build_trigger(self, node_type: str, config: dict):
        """Map a node config to an APScheduler trigger object, or None."""
        if node_type == _SCHEDULE_NODE_TYPE:
            expr = str(config.get("cron", "")).strip()
            if not expr:
                return None
            tz = str(config.get("timezone") or "UTC").strip() or "UTC"
            try:
                return CronTrigger.from_crontab(expr, timezone=tz)
            except Exception as e:  # noqa: BLE001
                logger.error(
                    "Invalid cron expression %r (tz=%s): %s", expr, tz, e
                )
                return None
        if node_type == _POLLING_NODE_TYPE:
            try:
                seconds = int(config.get("interval_seconds", 300))
            except (TypeError, ValueError):
                return None
            if seconds < 10:
                seconds = 10
            return IntervalTrigger(seconds=seconds)
        return None


# Module-level singleton used everywhere (main.py lifespan + router hooks).
scheduler_service = SchedulerService()


# ---------------------------------------------------------------- job callback
async def _run_workflow_job(
    workflow_id: int, trigger_node_type: str, trigger_node_id: str
) -> None:
    """APScheduler fires this when a schedule/polling job is due.

    Runs the full workflow with a fresh DB session and the appropriate
    TriggerType. Exceptions are caught + logged so APScheduler doesn't skip
    future fires because of a transient failure.
    """
    trigger_type = (
        TriggerType.POLLING
        if trigger_node_type == _POLLING_NODE_TYPE
        else TriggerType.SCHEDULE
    )
    db = SessionLocal()
    try:
        wf = db.query(Workflow).filter(Workflow.id == workflow_id).one_or_none()
        if wf is None:
            logger.warning(
                "Scheduled job fired for missing workflow %d (node %s)",
                workflow_id,
                trigger_node_id,
            )
            return
        if not wf.is_active:
            logger.info(
                "Skipping scheduled run for inactive workflow %d", workflow_id
            )
            return
        executor = WorkflowExecutor(db)
        execution = await executor.run(
            wf,
            trigger_type=trigger_type,
            trigger_input={
                "scheduled": True,
                "trigger_node_id": trigger_node_id,
            },
        )
        logger.info(
            "Scheduled run: workflow=%d execution=%d status=%s",
            workflow_id,
            execution.id,
            execution.status,
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "Scheduled job failed for workflow %d node %s",
            workflow_id,
            trigger_node_id,
        )
    finally:
        db.close()
