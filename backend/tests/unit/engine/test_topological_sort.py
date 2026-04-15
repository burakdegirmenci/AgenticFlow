"""Topological sort correctness and cycle detection."""

from __future__ import annotations

import pytest

from app.engine.errors import GraphError
from app.engine.executor import WorkflowExecutor


def _ids(*names: str) -> dict[str, dict]:
    return {n: {"id": n, "type": "noop", "data": {}} for n in names}


def _edge(src: str, tgt: str) -> dict:
    return {"id": f"{src}-{tgt}", "source": src, "target": tgt}


def test_linear_chain_is_sorted_source_to_sink(db_session) -> None:
    executor = WorkflowExecutor(db_session)
    nodes = _ids("a", "b", "c")
    edges = [_edge("a", "b"), _edge("b", "c")]

    order = executor._topological_sort(nodes, edges)

    assert order == ["a", "b", "c"]


def test_diamond_shape_is_valid(db_session) -> None:
    executor = WorkflowExecutor(db_session)
    nodes = _ids("root", "left", "right", "join")
    edges = [
        _edge("root", "left"),
        _edge("root", "right"),
        _edge("left", "join"),
        _edge("right", "join"),
    ]

    order = executor._topological_sort(nodes, edges)

    # root first, join last; left/right between.
    assert order[0] == "root"
    assert order[-1] == "join"
    assert set(order[1:3]) == {"left", "right"}


def test_multiple_roots_all_processed(db_session) -> None:
    executor = WorkflowExecutor(db_session)
    nodes = _ids("a", "b", "c")
    edges = [_edge("a", "c"), _edge("b", "c")]

    order = executor._topological_sort(nodes, edges)

    assert order[-1] == "c"
    assert set(order[:2]) == {"a", "b"}


def test_cycle_raises_graph_error(db_session) -> None:
    executor = WorkflowExecutor(db_session)
    nodes = _ids("a", "b", "c")
    edges = [_edge("a", "b"), _edge("b", "c"), _edge("c", "a")]

    with pytest.raises(GraphError, match="cycle"):
        executor._topological_sort(nodes, edges)


def test_dangling_edges_are_ignored(db_session) -> None:
    """Edges pointing to unknown node IDs must not confuse the sort."""
    executor = WorkflowExecutor(db_session)
    nodes = _ids("a", "b")
    edges = [
        _edge("a", "b"),
        _edge("a", "ghost"),  # target missing
        _edge("phantom", "b"),  # source missing
    ]

    order = executor._topological_sort(nodes, edges)

    assert order == ["a", "b"]


def test_empty_graph_yields_empty_order(db_session) -> None:
    executor = WorkflowExecutor(db_session)
    assert executor._topological_sort({}, []) == []


def test_isolated_nodes_still_emitted(db_session) -> None:
    executor = WorkflowExecutor(db_session)
    nodes = _ids("x", "y", "z")
    edges: list[dict] = []

    order = executor._topological_sort(nodes, edges)

    # Deterministic lex ordering for isolated nodes.
    assert order == ["x", "y", "z"]
