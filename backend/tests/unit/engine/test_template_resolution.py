"""Template substitution in node config values."""

from __future__ import annotations

from app.engine.executor import WorkflowExecutor


def _parents(**kw) -> dict:
    return dict(kw)


def test_simple_path_is_resolved(db_session) -> None:
    executor = WorkflowExecutor(db_session)
    resolved = executor._resolve_config(
        config={"message": "Hello {{n1.name}}"},
        parent_outputs=_parents(n1={"name": "Ali"}),
        schema={"properties": {"message": {"type": "string"}}},
    )
    assert resolved["message"] == "Hello Ali"


def test_integer_expected_type_coerces(db_session) -> None:
    executor = WorkflowExecutor(db_session)
    resolved = executor._resolve_config(
        config={"limit": "{{n1.count}}"},
        parent_outputs=_parents(n1={"count": 42}),
        schema={"properties": {"limit": {"type": "integer"}}},
    )
    assert resolved["limit"] == 42
    assert isinstance(resolved["limit"], int)


def test_number_expected_type_coerces(db_session) -> None:
    executor = WorkflowExecutor(db_session)
    resolved = executor._resolve_config(
        config={"ratio": "{{n1.r}}"},
        parent_outputs=_parents(n1={"r": 0.75}),
        schema={"properties": {"ratio": {"type": "number"}}},
    )
    assert resolved["ratio"] == 0.75
    assert isinstance(resolved["ratio"], float)


def test_boolean_coercion_variants(db_session) -> None:
    executor = WorkflowExecutor(db_session)
    for raw, expected in [("true", True), ("false", False), ("1", True), ("0", False)]:
        resolved = executor._resolve_config(
            config={"flag": "{{n1.v}}"},
            parent_outputs=_parents(n1={"v": raw}),
            schema={"properties": {"flag": {"type": "boolean"}}},
        )
        assert resolved["flag"] is expected, f"{raw!r} should coerce to {expected}"


def test_missing_path_keeps_placeholder(db_session) -> None:
    """If the expression can't be resolved, the user should SEE the placeholder."""
    executor = WorkflowExecutor(db_session)
    resolved = executor._resolve_config(
        config={"msg": "Hi {{n1.missing}}"},
        parent_outputs=_parents(n1={"name": "ok"}),
        schema={"properties": {"msg": {"type": "string"}}},
    )
    assert resolved["msg"] == "Hi {{n1.missing}}"


def test_nested_dict_config_is_walked(db_session) -> None:
    executor = WorkflowExecutor(db_session)
    resolved = executor._resolve_config(
        config={
            "payload": {
                "title": "{{n1.t}}",
                "items": ["{{n1.first}}", "static"],
            }
        },
        parent_outputs=_parents(n1={"t": "T", "first": "F"}),
        schema={"properties": {"payload": {"type": "object"}}},
    )
    assert resolved["payload"] == {
        "title": "T",
        "items": ["F", "static"],
    }


def test_shallow_merge_allows_bare_field_reference(db_session) -> None:
    """`flatten_inputs` merges parent dicts so {{StokKodu}} works without parent id."""
    executor = WorkflowExecutor(db_session)
    resolved = executor._resolve_config(
        config={"msg": "kod: {{StokKodu}}"},
        parent_outputs=_parents(n1={"StokKodu": "SK-001"}),
        schema={"properties": {"msg": {"type": "string"}}},
    )
    assert resolved["msg"] == "kod: SK-001"


def test_non_string_config_values_pass_through(db_session) -> None:
    executor = WorkflowExecutor(db_session)
    resolved = executor._resolve_config(
        config={"limit": 100, "active": True, "tags": ["a", "b"]},
        parent_outputs={},
        schema=None,
    )
    assert resolved == {"limit": 100, "active": True, "tags": ["a", "b"]}
