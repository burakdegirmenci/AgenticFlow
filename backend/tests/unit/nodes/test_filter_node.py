"""transform.filter — keep items matching a condition."""

from __future__ import annotations

import pytest

from app.nodes.transform.filter import FilterNode


@pytest.fixture
def node() -> FilterNode:
    return FilterNode()


async def test_eq_keeps_only_matching_items(node, execution_context) -> None:
    inputs = {
        "parent": [
            {"id": 1, "status": "active"},
            {"id": 2, "status": "inactive"},
            {"id": 3, "status": "active"},
        ]
    }

    out = await node.execute(
        execution_context,
        inputs,
        {"field": "status", "op": "eq", "value": "active"},
    )

    assert [x["id"] for x in out["items"]] == [1, 3]
    assert out["count"] == 2
    assert out["removed"] == 1


async def test_dotted_field_path(node, execution_context) -> None:
    inputs = {
        "parent": [
            {"id": 1, "kargo": {"firma": "Aras"}},
            {"id": 2, "kargo": {"firma": "MNG"}},
        ]
    }

    out = await node.execute(
        execution_context,
        inputs,
        {"field": "kargo.firma", "op": "eq", "value": "Aras"},
    )

    assert [x["id"] for x in out["items"]] == [1]


async def test_not_empty_filters_out_blank_values(node, execution_context) -> None:
    inputs = {
        "parent": [
            {"id": 1, "note": "ok"},
            {"id": 2, "note": ""},
            {"id": 3, "note": None},
            {"id": 4, "note": "x"},
        ]
    }

    out = await node.execute(
        execution_context,
        inputs,
        {"field": "note", "op": "not_empty", "value": ""},
    )

    assert [x["id"] for x in out["items"]] == [1, 4]


async def test_empty_list_returns_empty_result(node, execution_context) -> None:
    out = await node.execute(
        execution_context,
        {"parent": []},
        {"field": "anything", "op": "eq", "value": "x"},
    )

    assert out["items"] == []
    assert out["count"] == 0
    assert out["removed"] == 0
