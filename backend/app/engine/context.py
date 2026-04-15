"""Per-execution runtime context."""

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.models.site import Site


@dataclass
class ExecutionContext:
    """State passed between nodes during a single workflow run."""

    execution_id: int
    workflow_id: int
    site: Site
    db: Session
    trigger_input: dict[str, Any] = field(default_factory=dict)
    # Output of each node keyed by node_id
    node_outputs: dict[str, Any] = field(default_factory=dict)
    # Shared variables between nodes (can be set via "set variable" nodes)
    variables: dict[str, Any] = field(default_factory=dict)
    # Populated by the executor immediately before each node runs so that
    # nodes can scope per-node state (e.g. PollingSnapshot for only_new).
    current_node_id: str | None = None

    def get_node_output(self, node_id: str) -> Any:
        return self.node_outputs.get(node_id)

    def set_node_output(self, node_id: str, value: Any) -> None:
        self.node_outputs[node_id] = value
