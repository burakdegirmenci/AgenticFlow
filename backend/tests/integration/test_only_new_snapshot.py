"""transform.only_new — end-to-end snapshot semantics.

Integration test (touches the real PollingSnapshot table in-memory) because
only_new's whole job is to persist state across invocations.
"""

from __future__ import annotations

import pytest

from app.models.polling_snapshot import PollingSnapshot
from app.nodes.transform.only_new import OnlyNewNode

pytestmark = pytest.mark.integration


@pytest.fixture
def node() -> OnlyNewNode:
    return OnlyNewNode()


async def test_first_run_seeds_snapshot_and_emits_nothing(
    node, execution_context, db_session
) -> None:
    execution_context.current_node_id = "n1"
    inputs = {"parent": [{"SiparisId": 1}, {"SiparisId": 2}, {"SiparisId": 3}]}

    out = await node.execute(execution_context, inputs, {"id_field": "SiparisId"})

    assert out["first_run"] is True
    assert out["new_items"] == []  # thundering-herd guard
    assert out["total_seen"] == 3

    snap = (
        db_session.query(PollingSnapshot)
        .filter_by(workflow_id=execution_context.workflow_id, node_id="n1")
        .one()
    )
    assert set(snap.last_seen_ids) == {"1", "2", "3"}


async def test_first_run_with_emit_flag_emits_everything(
    node, execution_context, db_session
) -> None:
    execution_context.current_node_id = "n1"
    inputs = {"parent": [{"SiparisId": 10}, {"SiparisId": 20}]}

    out = await node.execute(
        execution_context,
        inputs,
        {"id_field": "SiparisId", "emit_on_first_run": True},
    )

    assert out["first_run"] is True
    assert {item["SiparisId"] for item in out["new_items"]} == {10, 20}
    assert out["count"] == 2


async def test_subsequent_run_emits_only_new_ids(node, execution_context, db_session) -> None:
    execution_context.current_node_id = "n1"

    # First run — seed with 1, 2, 3 (no emit)
    await node.execute(
        execution_context,
        {"parent": [{"SiparisId": 1}, {"SiparisId": 2}, {"SiparisId": 3}]},
        {"id_field": "SiparisId"},
    )
    db_session.commit()

    # Second run — 2, 3 are known; 4, 5 are new
    out = await node.execute(
        execution_context,
        {
            "parent": [
                {"SiparisId": 2},
                {"SiparisId": 3},
                {"SiparisId": 4},
                {"SiparisId": 5},
            ]
        },
        {"id_field": "SiparisId"},
    )

    assert out["first_run"] is False
    assert {item["SiparisId"] for item in out["new_items"]} == {4, 5}
    assert out["count"] == 2


async def test_items_without_id_field_are_ignored(node, execution_context, db_session) -> None:
    execution_context.current_node_id = "n1"

    # Seed first
    await node.execute(
        execution_context,
        {"parent": [{"ID": 1}]},
        {"id_field": "ID", "emit_on_first_run": True},
    )
    db_session.commit()

    out = await node.execute(
        execution_context,
        {"parent": [{"ID": 2}, {"no_id_here": True}, {"ID": None}, {"ID": 3}]},
        {"id_field": "ID"},
    )

    emitted_ids = {item.get("ID") for item in out["new_items"]}
    assert emitted_ids == {2, 3}


async def test_snapshot_is_per_node_id(node, execution_context, db_session) -> None:
    """Two nodes in the same workflow keep independent snapshots."""
    # Seed node A
    execution_context.current_node_id = "A"
    await node.execute(
        execution_context,
        {"parent": [{"ID": 1}]},
        {"id_field": "ID", "emit_on_first_run": True},
    )
    db_session.commit()

    # Node B in same workflow should treat itself as first-run
    execution_context.current_node_id = "B"
    out = await node.execute(
        execution_context,
        {"parent": [{"ID": 1}, {"ID": 2}]},
        {"id_field": "ID"},
    )
    assert out["first_run"] is True
    assert out["new_items"] == []
