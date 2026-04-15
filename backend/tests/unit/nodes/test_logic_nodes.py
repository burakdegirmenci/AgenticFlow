"""logic.if / logic.switch / logic.loop — branching and iteration."""

from __future__ import annotations

import pytest

from app.nodes.logic.if_condition import IfConditionNode
from app.nodes.logic.loop import LoopNode
from app.nodes.logic.switch import SwitchNode


# ---------------------------------------------------------------------------
# IfConditionNode
# ---------------------------------------------------------------------------
@pytest.fixture
def if_node() -> IfConditionNode:
    return IfConditionNode()


async def test_if_item_true_produces_true_branch(if_node, execution_context) -> None:
    inputs = {"parent": [{"status": "active"}]}
    out = await if_node.execute(
        execution_context,
        inputs,
        {"mode": "item", "field": "status", "op": "eq", "value": "active"},
    )
    assert out["value"] is True
    assert "true" in out["_branches"]


async def test_if_item_false_produces_false_branch(if_node, execution_context) -> None:
    inputs = {"parent": [{"status": "inactive"}]}
    out = await if_node.execute(
        execution_context,
        inputs,
        {"mode": "item", "field": "status", "op": "eq", "value": "active"},
    )
    assert out["value"] is False
    assert "false" in out["_branches"]


async def test_if_list_empty_mode(if_node, execution_context) -> None:
    out = await if_node.execute(execution_context, {"parent": []}, {"mode": "list_empty"})
    assert out["value"] is True


async def test_if_list_not_empty_mode(if_node, execution_context) -> None:
    out = await if_node.execute(
        execution_context,
        {"parent": [{"id": 1}]},
        {"mode": "list_not_empty"},
    )
    assert out["value"] is True


async def test_if_list_not_empty_returns_false_for_empty(if_node, execution_context) -> None:
    out = await if_node.execute(execution_context, {"parent": []}, {"mode": "list_not_empty"})
    assert out["value"] is False


# ---------------------------------------------------------------------------
# SwitchNode
# ---------------------------------------------------------------------------
@pytest.fixture
def switch_node() -> SwitchNode:
    return SwitchNode()


async def test_switch_matched_value_routes_to_matching_branch(
    switch_node, execution_context
) -> None:
    inputs = {"parent": [{"priority": "high"}]}
    out = await switch_node.execute(execution_context, inputs, {"field": "priority"})
    assert out["value"] == "high"
    assert "high" in out["_branches"]


async def test_switch_empty_list_falls_back_to_default(switch_node, execution_context) -> None:
    out = await switch_node.execute(
        execution_context,
        {"parent": []},
        {"field": "priority", "default_branch": "no_data"},
    )
    assert out["value"] == ""
    assert "no_data" in out["_branches"]


async def test_switch_missing_field_falls_back_to_default(switch_node, execution_context) -> None:
    out = await switch_node.execute(
        execution_context,
        {"parent": [{"other": 1}]},
        {"field": "priority", "default_branch": "fallback"},
    )
    assert out["value"] == ""
    assert "fallback" in out["_branches"]


# ---------------------------------------------------------------------------
# LoopNode
# ---------------------------------------------------------------------------
@pytest.fixture
def loop_node() -> LoopNode:
    return LoopNode()


async def test_loop_passes_through_items_with_count(loop_node, execution_context) -> None:
    inputs = {"parent": [{"id": i} for i in range(5)]}
    out = await loop_node.execute(execution_context, inputs, {})
    assert len(out["items"]) == 5
    assert out["count"] == 5


async def test_loop_respects_limit(loop_node, execution_context) -> None:
    inputs = {"parent": [{"id": i} for i in range(100)]}
    out = await loop_node.execute(execution_context, inputs, {"limit": 10})
    assert out["count"] == 10
    assert [item["id"] for item in out["items"]] == list(range(10))


async def test_loop_limit_zero_means_all(loop_node, execution_context) -> None:
    inputs = {"parent": [{"id": i} for i in range(3)]}
    out = await loop_node.execute(execution_context, inputs, {"limit": 0})
    assert out["count"] == 3


async def test_loop_empty_input_yields_empty_output(loop_node, execution_context) -> None:
    out = await loop_node.execute(execution_context, {"parent": []}, {})
    assert out == {"items": [], "count": 0}
