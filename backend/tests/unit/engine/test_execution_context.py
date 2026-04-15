"""ExecutionContext — per-run state passed between nodes."""

from __future__ import annotations

from app.engine.context import ExecutionContext


def test_set_and_get_node_output(site, db_session) -> None:
    ctx = ExecutionContext(
        execution_id=1,
        workflow_id=1,
        site=site,
        db=db_session,
    )

    ctx.set_node_output("n1", {"result": 42})

    assert ctx.get_node_output("n1") == {"result": 42}


def test_missing_node_output_returns_none(site, db_session) -> None:
    ctx = ExecutionContext(
        execution_id=1,
        workflow_id=1,
        site=site,
        db=db_session,
    )

    assert ctx.get_node_output("never_set") is None


def test_defaults_are_independent_between_instances(site, db_session) -> None:
    """Mutable default args are a classic Python trap — ensure fields use default_factory."""
    a = ExecutionContext(execution_id=1, workflow_id=1, site=site, db=db_session)
    b = ExecutionContext(execution_id=2, workflow_id=2, site=site, db=db_session)

    a.set_node_output("x", 1)
    a.variables["shared"] = "a"
    a.trigger_input["k"] = "v"

    assert b.node_outputs == {}
    assert b.variables == {}
    assert b.trigger_input == {}


def test_variables_bag_is_writable(site, db_session) -> None:
    ctx = ExecutionContext(execution_id=1, workflow_id=1, site=site, db=db_session)

    ctx.variables["user_id"] = 123
    ctx.variables["label"] = "vip"

    assert ctx.variables == {"user_id": 123, "label": "vip"}
