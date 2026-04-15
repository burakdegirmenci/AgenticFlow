"""Engine exception classes."""


class WorkflowError(Exception):
    """Base workflow execution error."""


class NodeError(WorkflowError):
    """Error during individual node execution."""

    def __init__(self, node_id: str, node_type: str, message: str):
        self.node_id = node_id
        self.node_type = node_type
        super().__init__(f"[{node_type}:{node_id}] {message}")


class GraphError(WorkflowError):
    """Invalid graph structure (cycle, missing node, etc)."""
