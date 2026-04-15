"""app.nodes.ai._common — template renderer used by executor and AI nodes."""

from __future__ import annotations

from app.nodes.ai._common import _get_path, flatten_inputs, render_template


class TestGetPath:
    def test_dict_traversal(self) -> None:
        assert _get_path({"a": {"b": {"c": 42}}}, "a.b.c") == 42

    def test_list_index(self) -> None:
        assert _get_path({"xs": [10, 20, 30]}, "xs.1") == 20

    def test_missing_returns_none(self) -> None:
        assert _get_path({}, "x.y") is None
        assert _get_path({"a": 1}, "a.b") is None
        assert _get_path({"xs": [1]}, "xs.9") is None


class TestRenderTemplate:
    def test_simple_substitution(self) -> None:
        assert render_template("Merhaba {{name}}", {"name": "Ali"}) == "Merhaba Ali"

    def test_dotted_path_substitution(self) -> None:
        assert (
            render_template("kod: {{urun.StokKodu}}", {"urun": {"StokKodu": "A-1"}}) == "kod: A-1"
        )

    def test_missing_placeholder_left_intact(self) -> None:
        assert render_template("kod: {{nope}}", {}) == "kod: {{nope}}"

    def test_empty_template_yields_empty_string(self) -> None:
        assert render_template("", {"a": 1}) == ""

    def test_dict_value_serialized_as_json(self) -> None:
        out = render_template("meta: {{data}}", {"data": {"k": "v", "n": 1}})
        assert '"k": "v"' in out
        assert '"n": 1' in out

    def test_list_value_serialized_as_json(self) -> None:
        out = render_template("tags: {{tags}}", {"tags": ["a", "b"]})
        assert '"a"' in out and '"b"' in out

    def test_whitespace_inside_expression_tolerated(self) -> None:
        assert render_template("{{  user.name  }}", {"user": {"name": "Ali"}}) == "Ali"


class TestFlattenInputs:
    def test_parent_keys_preserved(self) -> None:
        merged = flatten_inputs({"n1": {"a": 1}})
        assert merged["n1"] == {"a": 1}

    def test_shallow_merge_exposes_nested_fields(self) -> None:
        """Users should be able to write `{{StokKodu}}` without a parent prefix."""
        merged = flatten_inputs({"n1": {"StokKodu": "A-1"}, "n2": {"Adet": 5}})
        assert merged["StokKodu"] == "A-1"
        assert merged["Adet"] == 5

    def test_parent_key_wins_over_inner_on_conflict(self) -> None:
        """If a parent key and a child field collide, the parent-keyed lookup wins."""
        merged = flatten_inputs({"n1": {"n1": "inner"}})
        # The outer `n1` (the parent-id key) is kept; the inner field would only
        # surface via `{{n1.n1}}`.
        assert merged["n1"] == {"n1": "inner"}

    def test_non_dict_parent_values_still_preserved(self) -> None:
        merged = flatten_inputs({"n1": [1, 2, 3]})
        assert merged["n1"] == [1, 2, 3]
