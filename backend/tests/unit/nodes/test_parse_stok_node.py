"""transform.parse_stok — derive base (OzelAlan1) code from stok_kodu."""

from __future__ import annotations

import pytest

from app.nodes.transform.parse_stok import ParseStokNode, derive_base_stok


class TestDeriveBaseStok:
    """Pure function — base-code derivation rules."""

    @pytest.mark.parametrize(
        ("stok_kodu", "expected"),
        [
            # Multi-segment: strip up to 2 variant tail segments
            ("ABC-YS-01", "ABC"),
            ("ABC-GR-18", "ABC"),
            ("ABC-KMJ-378", "ABC"),
            # Mixed alphanumeric variant (EA4, hz4)
            ("MDL-EA4", "MDL"),
            ("MDL-hz4", "MDL"),
            # Single-char segments preserved (R, 7)
            ("ABC-R", "ABC-R"),
            ("ABC-7", "ABC-7"),
            # One-segment input returned as-is
            ("SIMPLE", "SIMPLE"),
            # Empty
            ("", ""),
            # Only strip up to max_strip (2) segments
            ("ABC-VAR1-VAR2-VAR3", "ABC-VAR1"),
            # Base itself is alpha-only short label (not a variant)
            ("X", "X"),
        ],
    )
    def test_rules(self, stok_kodu: str, expected: str) -> None:
        assert derive_base_stok(stok_kodu) == expected

    def test_custom_max_strip(self) -> None:
        assert derive_base_stok("A-01-02-03", max_strip=3) == "A"
        assert derive_base_stok("A-01-02-03", max_strip=1) == "A-01-02"


@pytest.fixture
def node() -> ParseStokNode:
    return ParseStokNode()


class TestParseStokNode:
    async def test_derives_base_into_configured_target(self, node, execution_context) -> None:
        inputs = {
            "parent": [
                {"StokKodu": "ABC-YS-01"},
                {"StokKodu": "XYZ-KMJ-378"},
            ]
        }
        out = await node.execute(
            execution_context,
            inputs,
            {"source_field": "StokKodu", "target_field": "OzelAlan1"},
        )
        assert [item["OzelAlan1"] for item in out["items"]] == ["ABC", "XYZ"]
        assert out["count"] == 2

    async def test_missing_source_field_leaves_target_empty(self, node, execution_context) -> None:
        inputs = {"parent": [{"OtherField": "x"}]}
        out = await node.execute(
            execution_context,
            inputs,
            {"source_field": "StokKodu", "target_field": "OzelAlan1"},
        )
        assert out["items"][0].get("OzelAlan1") == ""

    async def test_non_dict_items_pass_through(self, node, execution_context) -> None:
        inputs = {"parent": ["string-item", 42]}
        out = await node.execute(
            execution_context,
            inputs,
            {"source_field": "StokKodu", "target_field": "OzelAlan1"},
        )
        assert out["items"] == ["string-item", 42]
