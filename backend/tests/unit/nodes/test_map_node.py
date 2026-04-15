"""transform.map — pick/rename/add fields on each item."""

from __future__ import annotations

import pytest

from app.nodes.transform.map_node import MapNode


@pytest.fixture
def node() -> MapNode:
    return MapNode()


async def test_source_path_rewrites_field(node, execution_context) -> None:
    inputs = {
        "parent": [
            {"StokKodu": "A1", "Fiyat": 100},
            {"StokKodu": "B2", "Fiyat": 200},
        ]
    }
    out = await node.execute(
        execution_context,
        inputs,
        {"mappings": {"sku": "=StokKodu", "price": "=Fiyat"}},
    )
    assert out["items"] == [
        {"sku": "A1", "price": 100},
        {"sku": "B2", "price": 200},
    ]
    assert out["count"] == 2


async def test_literal_value_mapped_as_constant(node, execution_context) -> None:
    inputs = {"parent": [{"id": 1}, {"id": 2}]}
    out = await node.execute(
        execution_context,
        inputs,
        {"mappings": {"status": "active"}},
    )
    assert [item["status"] for item in out["items"]] == ["active", "active"]


async def test_keep_original_merges_new_onto_old(node, execution_context) -> None:
    inputs = {"parent": [{"a": 1, "b": 2}]}
    out = await node.execute(
        execution_context,
        inputs,
        {"mappings": {"c": "=a"}, "keep_original": True},
    )
    assert out["items"] == [{"a": 1, "b": 2, "c": 1}]


async def test_without_keep_original_only_mapped_fields_remain(node, execution_context) -> None:
    inputs = {"parent": [{"a": 1, "b": 2}]}
    out = await node.execute(execution_context, inputs, {"mappings": {"c": "=a"}})
    assert out["items"] == [{"c": 1}]


async def test_dotted_source_path(node, execution_context) -> None:
    inputs = {"parent": [{"kargo": {"firma": "Aras"}}]}
    out = await node.execute(execution_context, inputs, {"mappings": {"carrier": "=kargo.firma"}})
    assert out["items"] == [{"carrier": "Aras"}]


async def test_mappings_as_json_string(node, execution_context) -> None:
    """UI may pass mappings as raw JSON string."""
    inputs = {"parent": [{"x": 1}]}
    out = await node.execute(
        execution_context,
        inputs,
        {"mappings": '{"y": "=x"}'},
    )
    assert out["items"] == [{"y": 1}]


async def test_invalid_json_string_degrades_to_empty(node, execution_context) -> None:
    inputs = {"parent": [{"x": 1}]}
    out = await node.execute(
        execution_context,
        inputs,
        {"mappings": "{broken json"},
    )
    # no mappings → items are empty dicts (keep_original=False default)
    assert out["items"] == [{}]


async def test_non_dict_items_pass_through_unchanged(node, execution_context) -> None:
    inputs = {"parent": [1, "two", {"a": 1}]}
    out = await node.execute(execution_context, inputs, {"mappings": {"a": "=a"}})
    # non-dict items kept verbatim; dict items remapped
    assert out["items"] == [1, "two", {"a": 1}]
