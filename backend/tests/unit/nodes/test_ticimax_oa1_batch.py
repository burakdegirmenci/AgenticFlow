"""ticimax.urun.update_ozel_alan_1_batch — dry-run + skip paths.

The batch update node has three code paths that do NOT need a live
Ticimax client:
1. Dry-run mode — never calls SOAP, just emits what it WOULD have done.
2. Skip paths (``skip_has_oa1``, ``skip_no_sku``, ``skip_noop``,
   ``skip_same``) — decided before any SOAP call.
3. Error paths with no ID / abort threshold.

These cover the bulk of the interesting behavior without needing a zeep
factory mock. The actual `UrunKartiGuncelle` call path (non-dry-run) is
covered by the smoke scripts in ``scripts/legacy_scripts/`` until a
proper SOAP stub lands in a later sprint.
"""

from __future__ import annotations

import pytest

from app.nodes.ticimax.update_ozel_alan_1_batch import (
    UrunUpdateOzelAlan1BatchNode,
    _extract_first_stok_kodu,
)


# ---------------------------------------------------------------------------
# Pure helper: _extract_first_stok_kodu
# ---------------------------------------------------------------------------
class TestExtractFirstStokKodu:
    def test_list_of_variations(self) -> None:
        urun = {
            "Varyasyonlar": {
                "Varyasyon": [
                    {"StokKodu": "ABC-YS-01"},
                    {"StokKodu": "ABC-YS-02"},
                ]
            }
        }
        assert _extract_first_stok_kodu(urun) == "ABC-YS-01"

    def test_single_variation_as_dict(self) -> None:
        urun = {"Varyasyonlar": {"Varyasyon": {"StokKodu": "SKU-ONE"}}}
        assert _extract_first_stok_kodu(urun) == "SKU-ONE"

    def test_missing_varyasyonlar_returns_empty(self) -> None:
        assert _extract_first_stok_kodu({"ID": 1}) == ""

    def test_varyasyonlar_not_a_dict_returns_empty(self) -> None:
        assert _extract_first_stok_kodu({"Varyasyonlar": "not-a-dict"}) == ""

    def test_empty_list_returns_empty(self) -> None:
        urun = {"Varyasyonlar": {"Varyasyon": []}}
        assert _extract_first_stok_kodu(urun) == ""

    def test_varyasyon_missing_key_returns_empty(self) -> None:
        urun = {"Varyasyonlar": {}}
        assert _extract_first_stok_kodu(urun) == ""

    def test_first_variant_not_dict_returns_empty(self) -> None:
        urun = {"Varyasyonlar": {"Varyasyon": ["string", {"StokKodu": "X"}]}}
        assert _extract_first_stok_kodu(urun) == ""

    def test_none_stok_kodu_returns_empty(self) -> None:
        urun = {"Varyasyonlar": {"Varyasyon": [{"StokKodu": None}]}}
        assert _extract_first_stok_kodu(urun) == ""

    def test_whitespace_stok_kodu_is_stripped(self) -> None:
        urun = {"Varyasyonlar": {"Varyasyon": [{"StokKodu": "  ABC-YS  "}]}}
        assert _extract_first_stok_kodu(urun) == "ABC-YS"


# ---------------------------------------------------------------------------
# Dry-run path — no SOAP, just enumeration + stats
# ---------------------------------------------------------------------------
@pytest.fixture
def node() -> UrunUpdateOzelAlan1BatchNode:
    return UrunUpdateOzelAlan1BatchNode()


def _urun(
    id_: int,
    *,
    oa1: str = "",
    variants: list[str] | None = None,
    adi: str = "Product",
) -> dict:
    vlist = [{"StokKodu": v} for v in (variants or [])]
    return {
        "ID": id_,
        "UrunAdi": adi,
        "OzelAlan1": oa1,
        "Varyasyonlar": {"Varyasyon": vlist},
    }


class TestDryRun:
    async def test_empty_input_returns_zeros(self, node, execution_context) -> None:
        out = await node.execute(
            execution_context,
            {"parent": {"urunler": []}},
            {"dry_run": True},
        )
        assert out["updated_count"] == 0
        assert out["error_count"] == 0
        assert out["dry_run"] is True
        assert out["results"] == []

    async def test_skip_has_oa1_when_set_and_skip_flag_true(self, node, execution_context) -> None:
        items = [_urun(1, oa1="EXISTING", variants=["ABC-YS-01"])]
        out = await node.execute(
            execution_context,
            {"parent": {"urunler": items}},
            {"dry_run": True, "skip_if_has_oa1": True, "item_delay_ms": 0},
        )
        assert out["skip_has_oa1"] == 1
        assert out["updated_count"] == 0
        assert out["results"][0]["status"] == "skip_has_oa1"

    async def test_skip_no_sku_when_first_variant_empty(self, node, execution_context) -> None:
        items = [_urun(1, oa1="", variants=[])]
        out = await node.execute(
            execution_context,
            {"parent": {"urunler": items}},
            {"dry_run": True, "skip_if_has_oa1": False, "item_delay_ms": 0},
        )
        assert out["skip_no_sku"] == 1

    async def test_would_update_when_derived_differs_from_existing(
        self, node, execution_context
    ) -> None:
        items = [_urun(1, oa1="", variants=["ABC-YS-01"])]  # derives to "ABC"
        out = await node.execute(
            execution_context,
            {"parent": {"urunler": items}},
            {"dry_run": True, "skip_if_has_oa1": False, "item_delay_ms": 0},
        )
        assert out["updated_count"] == 1
        assert out["results"][0]["status"] in {"would_update", "dry_run"}
        # The derived value is surfaced
        result = out["results"][0]
        assert result.get("yeni_oa1") == "ABC" or result.get("derived_oa1") == "ABC"

    async def test_missing_id_counts_as_error(self, node, execution_context) -> None:
        items = [{"UrunAdi": "no-id", "Varyasyonlar": {"Varyasyon": []}}]
        out = await node.execute(
            execution_context,
            {"parent": {"urunler": items}},
            {"dry_run": True, "item_delay_ms": 0, "abort_on_consecutive_errors": 10},
        )
        assert out["error_count"] == 1
        assert out["results"][0]["status"] == "error"

    async def test_abort_on_consecutive_missing_ids(self, node, execution_context) -> None:
        from app.engine.errors import NodeError

        items = [
            {"UrunAdi": "no-id-1", "Varyasyonlar": {"Varyasyon": []}},
            {"UrunAdi": "no-id-2", "Varyasyonlar": {"Varyasyon": []}},
            {"UrunAdi": "no-id-3", "Varyasyonlar": {"Varyasyon": []}},
            # These would succeed if we ever got to them.
            _urun(1, variants=["A-01"]),
            _urun(2, variants=["B-01"]),
        ]
        # Hitting the consecutive-error threshold raises NodeError so the
        # workflow executor marks the step as ERROR.
        with pytest.raises(NodeError, match="consecutive errors"):
            await node.execute(
                execution_context,
                {"parent": {"urunler": items}},
                {
                    "dry_run": True,
                    "item_delay_ms": 0,
                    "abort_on_consecutive_errors": 3,
                },
            )

    async def test_urunler_path_resolves_nested(self, node, execution_context) -> None:
        items = [_urun(1, variants=["ABC-YS-01"])]
        out = await node.execute(
            execution_context,
            {"parent": {"result": {"UrunList": items}}},
            {
                "dry_run": True,
                "urunler_path": "result.UrunList",
                "skip_if_has_oa1": False,
                "item_delay_ms": 0,
            },
        )
        assert out["updated_count"] == 1

    async def test_bad_urunler_path_raises_node_error(self, node, execution_context) -> None:
        from app.engine.errors import NodeError

        with pytest.raises(NodeError):
            await node.execute(
                execution_context,
                {"parent": {"urunler": "not-a-list"}},
                {"dry_run": True, "item_delay_ms": 0},
            )
