"""DAG workflow executor - topological sort + sequential async execution.

MVP: Tek worker, sıralı topological execution. Her node için ExecutionStep
DB'ye düşer. Hata → step ERROR, execution ERROR. Parallel/retry/loop Faz 3.
"""

import time
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.engine.context import ExecutionContext
from app.engine.errors import GraphError
from app.models.execution import (
    Execution,
    ExecutionStatus,
    ExecutionStep,
    TriggerType,
)
from app.models.workflow import Workflow


class WorkflowExecutor:
    """Runs a workflow graph against a site."""

    def __init__(self, db: Session):
        self.db = db

    def create_execution(
        self,
        workflow: Workflow,
        trigger_type: TriggerType = TriggerType.MANUAL,
        trigger_input: dict | None = None,
        initial_status: ExecutionStatus = ExecutionStatus.RUNNING,
    ) -> Execution:
        """Create and persist a new Execution row, return it."""
        execution = Execution(
            workflow_id=workflow.id,
            status=initial_status,
            trigger_type=trigger_type,
            started_at=datetime.utcnow(),
            input_data=trigger_input or {},
        )
        self.db.add(execution)
        self.db.commit()
        self.db.refresh(execution)
        return execution

    async def run_existing(self, execution_id: int) -> Execution | None:
        """Resume / start an Execution row that was created earlier.

        Used by the async run endpoint, which inserts a PENDING Execution
        synchronously and dispatches the actual graph execution to a
        FastAPI BackgroundTask. The background task gets a fresh DB session
        and calls this method.
        """
        execution = self.db.query(Execution).filter(Execution.id == execution_id).first()
        if not execution:
            return None
        workflow = self.db.query(Workflow).filter(Workflow.id == execution.workflow_id).first()
        if not workflow:
            execution.status = ExecutionStatus.ERROR
            execution.error = "Workflow not found"
            execution.finished_at = datetime.utcnow()
            self.db.commit()
            return execution
        return await self._execute_graph(
            workflow,
            execution,
            trigger_input=execution.input_data or {},
        )

    async def run(
        self,
        workflow: Workflow,
        trigger_type: TriggerType = TriggerType.MANUAL,
        trigger_input: dict | None = None,
    ) -> Execution:
        """Execute the full workflow, returns completed Execution row.

        Convenience entry point used by the scheduler and tests; the
        interactive UI route uses ``create_execution`` + ``run_existing``
        for early acknowledgement.
        """
        execution = self.create_execution(
            workflow,
            trigger_type=trigger_type,
            trigger_input=trigger_input,
            initial_status=ExecutionStatus.RUNNING,
        )
        return await self._execute_graph(workflow, execution, trigger_input=trigger_input or {})

    async def _execute_graph(
        self,
        workflow: Workflow,
        execution: Execution,
        trigger_input: dict | None = None,
    ) -> Execution:
        """Run the topological order against an existing Execution row."""
        from app.nodes import NODE_REGISTRY  # lazy to avoid circular

        # Promote PENDING → RUNNING when the worker actually starts.
        if execution.status == ExecutionStatus.PENDING:
            execution.status = ExecutionStatus.RUNNING
            execution.started_at = datetime.utcnow()
            self.db.commit()

        site = workflow.site
        context = ExecutionContext(
            execution_id=execution.id,
            workflow_id=workflow.id,
            site=site,
            db=self.db,
            trigger_input=trigger_input or {},
        )

        graph = workflow.graph_json or {"nodes": [], "edges": []}
        nodes_by_id: dict[str, dict] = {n["id"]: n for n in graph.get("nodes", [])}
        edges: list[dict] = graph.get("edges", [])

        try:
            order = self._topological_sort(nodes_by_id, edges)
        except GraphError as e:
            execution.status = ExecutionStatus.ERROR
            execution.error = str(e)
            execution.finished_at = datetime.utcnow()
            self.db.commit()
            return execution

        # 2. Execute nodes in order
        skipped_nodes: set[str] = set()
        for node_id in order:
            node_data = nodes_by_id[node_id]
            node_type = node_data.get("type", "")
            node_config = (node_data.get("data") or {}).get("config") or {}

            # Skip if all parents were skipped or their branches do not reach us
            incoming = [e for e in edges if e.get("target") == node_id]
            if incoming and not self._has_active_incoming(incoming, skipped_nodes, context):
                skipped_nodes.add(node_id)
                self._record_step(
                    execution.id,
                    node_id,
                    node_type,
                    ExecutionStatus.SKIPPED,
                    error="",
                )
                continue

            node_cls = NODE_REGISTRY.get(node_type)
            if node_cls is None:
                self._record_step_error(
                    execution.id, node_id, node_type, f"Unknown node type: {node_type}"
                )
                execution.status = ExecutionStatus.ERROR
                execution.error = f"Unknown node type: {node_type}"
                break

            # Gather inputs from parent edges (skipped parents excluded)
            parent_outputs = self._collect_parent_outputs(node_id, edges, context, skipped_nodes)

            step = ExecutionStep(
                execution_id=execution.id,
                node_id=node_id,
                node_type=node_type,
                status=ExecutionStatus.RUNNING,
                started_at=datetime.utcnow(),
                input_data=self._safe_json(parent_outputs),
            )
            self.db.add(step)
            self.db.commit()

            t_start = time.time()
            try:
                node_instance = node_cls()
                resolved_config = self._resolve_config(
                    node_config,
                    parent_outputs,
                    getattr(node_cls, "config_schema", None),
                )
                context.current_node_id = node_id
                output = await node_instance.execute(context, parent_outputs, resolved_config)
                context.set_node_output(node_id, output)

                step.status = ExecutionStatus.SUCCESS
                step.output_data = self._safe_json(output)
            except Exception as e:
                step.status = ExecutionStatus.ERROR
                step.error = str(e)[:2000]
                execution.status = ExecutionStatus.ERROR
                execution.error = f"[{node_type}:{node_id}] {e}"[:2000]

            step.finished_at = datetime.utcnow()
            step.duration_ms = int((time.time() - t_start) * 1000)
            self.db.commit()

            if execution.status == ExecutionStatus.ERROR:
                break

        # 3. Finalize
        if execution.status != ExecutionStatus.ERROR:
            execution.status = ExecutionStatus.SUCCESS
        execution.finished_at = datetime.utcnow()
        execution.output_data = self._safe_json(context.node_outputs)
        self.db.commit()
        self.db.refresh(execution)
        return execution

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------
    def _topological_sort(self, nodes_by_id: dict[str, dict], edges: list[dict]) -> list[str]:
        """Kahn's algorithm - raise GraphError on cycle."""
        in_degree: dict[str, int] = {nid: 0 for nid in nodes_by_id}
        adj: dict[str, list[str]] = {nid: [] for nid in nodes_by_id}

        for edge in edges:
            src = edge.get("source")
            tgt = edge.get("target")
            if src not in nodes_by_id or tgt not in nodes_by_id:
                continue
            adj[src].append(tgt)
            in_degree[tgt] += 1

        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        order: list[str] = []

        while queue:
            # Deterministic order: pick lexicographically smallest
            queue.sort()
            nid = queue.pop(0)
            order.append(nid)
            for child in adj[nid]:
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        if len(order) != len(nodes_by_id):
            raise GraphError("Workflow graph contains a cycle")

        return order

    def _has_active_incoming(
        self,
        incoming: list[dict],
        skipped_nodes: set[str],
        context: ExecutionContext,
    ) -> bool:
        """Return True if at least one incoming edge is active.

        An edge is active when its source was not skipped AND either the
        source produced no `_branches` signal (all outgoing edges are
        active by default) OR the edge's `sourceHandle` matches one of
        the produced branch values.
        """
        for edge in incoming:
            src = edge.get("source")
            if not src or src in skipped_nodes:
                continue
            src_output = context.node_outputs.get(src)
            if not isinstance(src_output, dict):
                # Parent ran but produced a non-dict (or None) → treat as active
                return True
            branches = src_output.get("_branches")
            if not branches:
                return True
            handle = edge.get("sourceHandle") or ""
            active_branches = [str(b) for b in branches]
            if handle in active_branches:
                return True
            # Empty handle with no explicit match: active only if the node
            # emitted a single branch (implicit fall-through)
            if not handle and len(active_branches) == 1:
                return True
        return False

    def _collect_parent_outputs(
        self,
        node_id: str,
        edges: list[dict],
        context: ExecutionContext,
        skipped_nodes: set[str],
    ) -> dict[str, Any]:
        """Gather outputs from non-skipped parent nodes feeding into node_id."""
        parents: dict[str, Any] = {}
        for edge in edges:
            if edge.get("target") == node_id:
                src = edge.get("source")
                if src and src not in skipped_nodes and src in context.node_outputs:
                    parents[src] = context.node_outputs[src]
        return parents

    def _record_step(
        self,
        execution_id: int,
        node_id: str,
        node_type: str,
        status: ExecutionStatus,
        error: str = "",
    ) -> None:
        """Insert a terminal ExecutionStep row (used for SKIPPED nodes)."""
        now = datetime.utcnow()
        step = ExecutionStep(
            execution_id=execution_id,
            node_id=node_id,
            node_type=node_type,
            status=status,
            started_at=now,
            finished_at=now,
            duration_ms=0,
            error=error or "",
        )
        self.db.add(step)
        self.db.commit()

    def _record_step_error(
        self, execution_id: int, node_id: str, node_type: str, error: str
    ) -> None:
        step = ExecutionStep(
            execution_id=execution_id,
            node_id=node_id,
            node_type=node_type,
            status=ExecutionStatus.ERROR,
            started_at=datetime.utcnow(),
            finished_at=datetime.utcnow(),
            error=error,
        )
        self.db.add(step)
        self.db.commit()

    def _safe_json(self, value: Any) -> Any:
        """Ensure the value is JSON-serializable (best effort)."""
        try:
            import json

            json.dumps(value, default=str)
            return value
        except Exception:
            return {"_repr": str(value)[:5000]}

    def _resolve_config(
        self,
        config: dict[str, Any],
        parent_outputs: dict[str, Any],
        schema: dict | None,
    ) -> dict[str, Any]:
        """Render ``{{path.to.field}}`` templates in config string values.

        This lets every node (including the 237 auto-generated Ticimax nodes)
        reference parent outputs in their config. Uses the same template engine
        as ``ai.prompt`` so behavior is consistent across the catalog.

        Type coercion: if the JSON Schema says a field is ``integer`` or
        ``number``, the rendered string is cast accordingly so SOAP parameters
        get the right Python type. Falls back to the string on failed casts.
        """
        from app.nodes.ai._common import flatten_inputs, render_template

        ctx = flatten_inputs(parent_outputs or {})
        props: dict[str, dict] = {}
        if isinstance(schema, dict):
            props = schema.get("properties") or {}

        def _render_value(val: Any, expected_type: str | None) -> Any:
            if isinstance(val, str):
                rendered = render_template(val, ctx)
                if expected_type == "integer":
                    try:
                        return int(rendered)
                    except (ValueError, TypeError):
                        return rendered
                if expected_type == "number":
                    try:
                        return float(rendered)
                    except (ValueError, TypeError):
                        return rendered
                if expected_type == "boolean":
                    if isinstance(rendered, str):
                        low = rendered.strip().lower()
                        if low in ("true", "1", "yes"):
                            return True
                        if low in ("false", "0", "no"):
                            return False
                    return rendered
                return rendered
            if isinstance(val, list):
                return [_render_value(v, None) for v in val]
            if isinstance(val, dict):
                return {k: _render_value(v, None) for k, v in val.items()}
            return val

        out: dict[str, Any] = {}
        for key, val in (config or {}).items():
            prop = props.get(key) or {}
            out[key] = _render_value(val, prop.get("type"))
        return out
