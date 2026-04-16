"""Registry-wide contract test.

This test runs against every node in ``NODE_REGISTRY`` and asserts the
contract defined in ``docs/SPECIFICATION.md §7`` and ``docs/IMPLEMENTATION.md §4``.

Any new node — hand-written or auto-generated — that breaks the contract
will break this test. That is the point.
"""

from __future__ import annotations

import inspect
import re

import pytest

from app.engine.node_base import BaseNode
from app.nodes import NODE_REGISTRY

# Valid type_id: `{category}.{domain}[.{action}...]` — lowercase, dot-separated,
# underscores allowed inside a segment. Examples:
#   ticimax.urun.select
#   transform.only_new
#   ai.prompt
_TYPE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$")

_ALLOWED_CATEGORIES = {
    "trigger",
    "input",
    "ticimax",
    "transform",
    "logic",
    "ai",
    "output",
    "control",  # reserved for future use
}

_REQUIRED_CLASSVARS = (
    "type_id",
    "category",
    "display_name",
)


pytestmark = pytest.mark.contract


@pytest.fixture(scope="module")
def registry() -> dict[str, type[BaseNode]]:
    assert NODE_REGISTRY, "NODE_REGISTRY is empty — are nodes being imported?"
    return dict(NODE_REGISTRY)


def test_registry_is_non_empty(registry) -> None:
    # Sanity: >= 3 triggers + a handful of transforms + 237 auto-gen ≫ 100.
    assert len(registry) >= 100, f"Registry has only {len(registry)} nodes"


def test_every_key_matches_class_type_id(registry) -> None:
    for key, cls in registry.items():
        assert cls.type_id == key, f"Registry key {key!r} != {cls.__name__}.type_id {cls.type_id!r}"


def test_every_node_subclasses_basenode(registry) -> None:
    for cls in registry.values():
        assert issubclass(cls, BaseNode), f"{cls.__name__} must subclass BaseNode"


def test_every_node_has_required_classvars(registry) -> None:
    missing: list[str] = []
    for cls in registry.values():
        for attr in _REQUIRED_CLASSVARS:
            val = getattr(cls, attr, None)
            if not val:
                missing.append(f"{cls.__name__}.{attr}")
    assert not missing, "Nodes missing required class vars:\n  " + "\n  ".join(missing)


def test_every_type_id_matches_pattern(registry) -> None:
    bad = [t for t in registry if not _TYPE_ID_RE.match(t)]
    assert not bad, (
        f"type_id must be lowercase dotted (e.g. `ticimax.urun.select`). Offenders: {bad}"
    )


def test_every_category_is_allowed(registry) -> None:
    unknown: dict[str, str] = {}
    for cls in registry.values():
        if cls.category not in _ALLOWED_CATEGORIES:
            unknown[cls.type_id] = cls.category
    assert not unknown, f"Unknown categories: {unknown}"


def test_type_id_prefix_matches_category(registry) -> None:
    """`type_id` first segment should match `category` (or 'trigger'/'ticimax' etc)."""
    mismatches: list[str] = []
    for cls in registry.values():
        prefix = cls.type_id.split(".", 1)[0]
        if prefix != cls.category:
            mismatches.append(f"{cls.type_id} (category={cls.category})")
    assert not mismatches, "type_id prefix must equal category:\n  " + "\n  ".join(mismatches)


def test_every_node_declares_execute(registry) -> None:
    for cls in registry.values():
        assert hasattr(cls, "execute"), f"{cls.__name__} missing execute()"
        assert inspect.iscoroutinefunction(cls.execute), (
            f"{cls.__name__}.execute must be `async def`"
        )


def test_every_node_has_json_schema_shaped_config(registry) -> None:
    """config_schema should be a dict with at least a `type` field (or empty {})."""
    bad: list[str] = []
    for cls in registry.values():
        schema = getattr(cls, "config_schema", None)
        if not isinstance(schema, dict):
            bad.append(f"{cls.type_id}: config_schema is {type(schema).__name__}")
            continue
        if schema and "type" not in schema and "properties" not in schema:
            bad.append(f"{cls.type_id}: config_schema missing `type`/`properties`")
    assert not bad, "Invalid config_schema:\n  " + "\n  ".join(bad)


def test_catalog_entry_is_json_serializable(registry) -> None:
    """Catalog feeds the frontend; any non-JSON value would break it."""
    import json

    for cls in registry.values():
        entry = cls.to_catalog_entry()
        try:
            json.dumps(entry)
        except (TypeError, ValueError) as e:
            pytest.fail(f"{cls.type_id} catalog entry not JSON serializable: {e}")


def test_no_duplicate_display_names_within_same_category(registry) -> None:
    """Two nodes with the same human label in the same palette section confuses users."""
    by_category: dict[str, dict[str, list[str]]] = {}
    for cls in registry.values():
        by_category.setdefault(cls.category, {}).setdefault(cls.display_name, []).append(
            cls.type_id
        )
    dupes = {
        cat: {name: ids for name, ids in items.items() if len(ids) > 1}
        for cat, items in by_category.items()
    }
    dupes = {k: v for k, v in dupes.items() if v}
    assert not dupes, f"Duplicate display_name within category: {dupes}"
