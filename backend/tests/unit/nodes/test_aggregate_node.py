"""transform.aggregate — count / sum / avg / min / max / group_by."""

from __future__ import annotations

import pytest

from app.nodes.transform.aggregate import AggregateNode


@pytest.fixture
def node() -> AggregateNode:
    return AggregateNode()


async def test_count_returns_length(node, execution_context) -> None:
    inputs = {"parent": [{"id": 1}, {"id": 2}, {"id": 3}]}
    out = await node.execute(execution_context, inputs, {"operation": "count"})
    assert out["result"] == {"count": 3}


async def test_count_empty_list(node, execution_context) -> None:
    out = await node.execute(execution_context, {"parent": []}, {"operation": "count"})
    assert out["result"] == {"count": 0}


async def test_sum_numeric_field(node, execution_context) -> None:
    inputs = {"parent": [{"price": 10}, {"price": 20.5}, {"price": "5"}]}
    out = await node.execute(execution_context, inputs, {"operation": "sum", "field": "price"})
    assert out["result"] == {"sum": 35.5, "count": 3}


async def test_sum_skips_non_numeric_and_missing(node, execution_context) -> None:
    inputs = {
        "parent": [
            {"price": 10},
            {"price": "not a number"},
            {},
            {"price": 5},
        ]
    }
    out = await node.execute(execution_context, inputs, {"operation": "sum", "field": "price"})
    assert out["result"] == {"sum": 15.0, "count": 2}


async def test_avg_min_max(node, execution_context) -> None:
    inputs = {"parent": [{"v": 2}, {"v": 4}, {"v": 6}]}
    for op, expected in [("avg", 4), ("min", 2), ("max", 6)]:
        out = await node.execute(execution_context, inputs, {"operation": op, "field": "v"})
        assert out["result"][op] == expected


async def test_numeric_op_all_missing_returns_none(node, execution_context) -> None:
    inputs = {"parent": [{"other": 1}, {"other": 2}]}
    out = await node.execute(execution_context, inputs, {"operation": "sum", "field": "price"})
    assert out["result"] == {"sum": None, "count": 0}


async def test_group_by_field(node, execution_context) -> None:
    inputs = {
        "parent": [
            {"cat": "a", "id": 1},
            {"cat": "b", "id": 2},
            {"cat": "a", "id": 3},
        ]
    }
    out = await node.execute(execution_context, inputs, {"operation": "group_by", "field": "cat"})
    groups = out["result"]["groups"]
    assert set(groups.keys()) == {"a", "b"}
    assert groups["a"]["count"] == 2
    assert groups["b"]["count"] == 1
    assert out["result"]["group_count"] == 2


async def test_group_by_missing_field_uses_underscore_bucket(node, execution_context) -> None:
    inputs = {"parent": [{"id": 1}, {"id": 2}]}
    out = await node.execute(execution_context, inputs, {"operation": "group_by", "field": ""})
    groups = out["result"]["groups"]
    assert "_" in groups
    assert groups["_"]["count"] == 2
