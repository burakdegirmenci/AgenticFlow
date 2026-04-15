"""Batch update node: derive and write OzelAlan1 for each product.

Consumes the `urunler` list produced by ``ticimax.urun.select`` and for
each product:
  1. Extracts the first variation's ``StokKodu`` from
     ``urun.Varyasyonlar.Varyasyon[0].StokKodu``.
  2. Derives the base code via ``derive_base_stok`` (from
     ``transform.parse_stok``) — strips up to 2 trailing variant
     segments (color/number codes).
  3. Compares the derived value with the existing ``OzelAlan1``.
  4. If different (and not empty / not equal to stok itself), calls
     ``UrunKartiGuncelle`` with ``OzelAlan1`` + ``OzelAlan1Guncelle=True``.
     Explicitly does NOT touch any other field.

Skip reasons mirror the original worker (``ProductDetail/worker/worker.py``):
  - ``skip_no_id``: product has no ID
  - ``skip_has_oa1``: existing OzelAlan1 already set (only when
    ``skip_if_has_oa1`` is True — preserves manually entered values)
  - ``skip_no_sku``: first variation has no stok kodu
  - ``skip_noop``: parse produced empty or identical stok (single segment)
  - ``skip_same``: existing OzelAlan1 already matches derived value

Supports ``dry_run`` — when true, nothing is sent to Ticimax but the node
still iterates and returns what it would have written. Abort policy: if
``abort_on_consecutive_errors`` updates fail in a row the node raises
NodeError and the workflow stops. Counter resets on every success.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.engine.context import ExecutionContext
from app.engine.errors import NodeError
from app.engine.node_base import BaseNode
from app.nodes import register
from app.nodes.ai._common import _get_path, flatten_inputs
from app.nodes.transform.parse_stok import derive_base_stok
from app.services.ticimax_service import TicimaxService


def _extract_first_stok_kodu(urun: dict[str, Any]) -> str:
    """Read ``Varyasyonlar.Varyasyon[0].StokKodu`` from a serialized product.

    Ticimax returns ``Varyasyonlar`` as a dict wrapping a ``Varyasyon`` list
    (or a single dict if only one variation exists). We accept both forms.
    """
    v = urun.get("Varyasyonlar")
    if not isinstance(v, dict):
        return ""
    vlist = v.get("Varyasyon")
    if vlist is None:
        return ""
    if not isinstance(vlist, list):
        vlist = [vlist]
    if not vlist:
        return ""
    first = vlist[0]
    if not isinstance(first, dict):
        return ""
    stok = first.get("StokKodu")
    return (str(stok) if stok is not None else "").strip()


@register
class UrunUpdateOzelAlan1BatchNode(BaseNode):
    type_id = "ticimax.urun.update_ozel_alan_1_batch"
    category = "ticimax"
    display_name = "OzelAlan1 Güncelle (Batch)"
    description = (
        "ticimax.urun.select'ten gelen ürün listesindeki her ürün için "
        "ilk varyasyonun stok kodundan OzelAlan1 değerini türetir "
        "(transform.parse_stok kuralı) ve farklıysa Ticimax'ta günceller. "
        "Diğer ürün alanlarına dokunmaz. Üst üste N hata olursa durdurur."
    )
    icon = "tag"
    color = "#0ea5e9"

    input_schema = {
        "type": "object",
        "properties": {"urunler": {"type": "array"}},
    }

    output_schema = {
        "type": "object",
        "properties": {
            "updated_count": {"type": "integer"},
            "error_count": {"type": "integer"},
            "skipped_count": {"type": "integer"},
            "skip_has_oa1": {"type": "integer"},
            "skip_no_sku": {"type": "integer"},
            "skip_noop": {"type": "integer"},
            "skip_same": {"type": "integer"},
            "dry_run": {"type": "boolean"},
            "aborted": {"type": "boolean"},
            "results": {"type": "array"},
        },
    }

    config_schema = {
        "type": "object",
        "properties": {
            "urunler_path": {
                "type": "string",
                "title": "Ürün Listesi Path'i",
                "description": (
                    "Flattened input içinde ürün dizisinin yolu. "
                    "Boş = parent'tan 'urunler' alanını bul."
                ),
                "default": "urunler",
            },
            "max_strip": {
                "type": "integer",
                "title": "Maks. Atılacak Segment",
                "description": "parse_stok ile aynı kural; kaç trailing varyant segmenti atılabilir.",
                "default": 2,
                "minimum": 0,
                "maximum": 5,
            },
            "dry_run": {
                "type": "boolean",
                "title": "Dry Run (yazma, sadece log)",
                "default": True,
            },
            "skip_if_has_oa1": {
                "type": "boolean",
                "title": "OzelAlan1 Dolu Olanları Atla",
                "description": (
                    "Ticimax UrunFiltre'de OzelAlan1 alanı yok, bu yüzden "
                    "sunucudan filtreleme mümkün değil. Bu seçenek açıkken, "
                    "fetch edilen ürünlerden OzelAlan1 değeri zaten dolu "
                    "olanlar parse/update aşamasına girmeden atlanır. "
                    "Manuel girilmiş değerleri korur."
                ),
                "default": True,
            },
            "item_delay_ms": {
                "type": "integer",
                "title": "Öğeler Arası Bekleme (ms)",
                "default": 150,
                "minimum": 0,
                "maximum": 60000,
            },
            "abort_on_consecutive_errors": {
                "type": "integer",
                "title": "Ardışık Hata Eşiği",
                "default": 3,
                "minimum": 1,
                "maximum": 100,
            },
        },
    }

    async def execute(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        urunler_path = str(config.get("urunler_path", "urunler")).strip() or "urunler"
        max_strip = int(config.get("max_strip", 2))
        dry_run = bool(config.get("dry_run", True))
        skip_if_has_oa1 = bool(config.get("skip_if_has_oa1", True))
        delay_sec = int(config.get("item_delay_ms", 150)) / 1000.0
        abort_threshold = int(config.get("abort_on_consecutive_errors", 3))

        merged = flatten_inputs(inputs)
        raw = _get_path(merged, urunler_path)
        if raw is None and "urunler" in merged:
            raw = merged["urunler"]

        if not isinstance(raw, list):
            raise NodeError(
                "",
                self.type_id,
                f"urunler_path '{urunler_path}' did not resolve to a list "
                f"(got {type(raw).__name__})",
            )

        items: list[dict[str, Any]] = [u for u in raw if isinstance(u, dict)]

        if not items:
            return {
                "updated_count": 0,
                "error_count": 0,
                "skipped_count": 0,
                "skip_has_oa1": 0,
                "skip_no_sku": 0,
                "skip_noop": 0,
                "skip_same": 0,
                "dry_run": dry_run,
                "aborted": False,
                "results": [],
            }

        client = None
        if not dry_run:
            client = TicimaxService.get_client(context.site)

        out_results: list[dict[str, Any]] = []
        updated = 0
        errors = 0
        skip_has_oa1 = 0
        skip_no_sku = 0
        skip_noop = 0
        skip_same = 0
        consecutive_errors = 0

        for idx, urun in enumerate(items):
            urun_karti_id = urun.get("ID") or urun.get("UrunKartiID")
            urun_adi = (urun.get("UrunAdi") or "").strip()
            eski_oa1 = (urun.get("OzelAlan1") or "").strip()

            if not urun_karti_id:
                errors += 1
                consecutive_errors += 1
                out_results.append(
                    {
                        "index": idx,
                        "urun_karti_id": None,
                        "urun_adi": urun_adi,
                        "status": "error",
                        "error": "missing ID / UrunKartiID",
                    }
                )
                if consecutive_errors >= abort_threshold:
                    return self._abort(
                        out_results,
                        updated,
                        errors,
                        skip_has_oa1,
                        skip_no_sku,
                        skip_noop,
                        skip_same,
                        dry_run,
                    )
                continue

            # Early skip: OzelAlan1 already set → preserve manual/existing value
            if skip_if_has_oa1 and eski_oa1:
                skip_has_oa1 += 1
                out_results.append(
                    {
                        "index": idx,
                        "urun_karti_id": urun_karti_id,
                        "urun_adi": urun_adi,
                        "eski_oa1": eski_oa1,
                        "status": "skip_has_oa1",
                    }
                )
                continue

            stok_kodu = _extract_first_stok_kodu(urun)
            if not stok_kodu:
                skip_no_sku += 1
                out_results.append(
                    {
                        "index": idx,
                        "urun_karti_id": urun_karti_id,
                        "urun_adi": urun_adi,
                        "stok_kodu": "",
                        "eski_oa1": eski_oa1,
                        "yeni_oa1": "",
                        "status": "skip_no_sku",
                    }
                )
                continue

            yeni_oa1 = derive_base_stok(stok_kodu, max_strip=max_strip)
            if not yeni_oa1 or yeni_oa1 == stok_kodu:
                skip_noop += 1
                out_results.append(
                    {
                        "index": idx,
                        "urun_karti_id": urun_karti_id,
                        "urun_adi": urun_adi,
                        "stok_kodu": stok_kodu,
                        "eski_oa1": eski_oa1,
                        "yeni_oa1": yeni_oa1,
                        "status": "skip_noop",
                    }
                )
                continue

            if eski_oa1 and eski_oa1 == yeni_oa1:
                skip_same += 1
                out_results.append(
                    {
                        "index": idx,
                        "urun_karti_id": urun_karti_id,
                        "urun_adi": urun_adi,
                        "stok_kodu": stok_kodu,
                        "eski_oa1": eski_oa1,
                        "yeni_oa1": yeni_oa1,
                        "status": "skip_same",
                    }
                )
                continue

            # Needs update
            if dry_run:
                updated += 1
                consecutive_errors = 0
                out_results.append(
                    {
                        "index": idx,
                        "urun_karti_id": urun_karti_id,
                        "urun_adi": urun_adi,
                        "stok_kodu": stok_kodu,
                        "eski_oa1": eski_oa1,
                        "yeni_oa1": yeni_oa1,
                        "status": "dry_run",
                    }
                )
            else:
                try:
                    await self._update_one(client, int(urun_karti_id), yeni_oa1)
                    updated += 1
                    consecutive_errors = 0
                    out_results.append(
                        {
                            "index": idx,
                            "urun_karti_id": urun_karti_id,
                            "urun_adi": urun_adi,
                            "stok_kodu": stok_kodu,
                            "eski_oa1": eski_oa1,
                            "yeni_oa1": yeni_oa1,
                            "status": "updated",
                        }
                    )
                except Exception as e:
                    errors += 1
                    consecutive_errors += 1
                    out_results.append(
                        {
                            "index": idx,
                            "urun_karti_id": urun_karti_id,
                            "urun_adi": urun_adi,
                            "stok_kodu": stok_kodu,
                            "eski_oa1": eski_oa1,
                            "yeni_oa1": yeni_oa1,
                            "status": "error",
                            "error": str(e)[:500],
                        }
                    )
                    if consecutive_errors >= abort_threshold:
                        return self._abort(
                            out_results,
                            updated,
                            errors,
                            skip_has_oa1,
                            skip_no_sku,
                            skip_noop,
                            skip_same,
                            dry_run,
                        )

            if delay_sec > 0 and idx < len(items) - 1:
                await asyncio.sleep(delay_sec)

        return {
            "updated_count": updated,
            "error_count": errors,
            "skipped_count": skip_has_oa1 + skip_no_sku + skip_noop + skip_same,
            "skip_has_oa1": skip_has_oa1,
            "skip_no_sku": skip_no_sku,
            "skip_noop": skip_noop,
            "skip_same": skip_same,
            "dry_run": dry_run,
            "aborted": False,
            "results": out_results,
        }

    # ------------------------------------------------------------------
    async def _update_one(self, client: Any, urun_karti_id: int, yeni_oa1: str) -> None:
        """Single UrunKartiGuncelle call — runs the blocking SOAP in a thread.

        Uses the same partial-update pattern as the original worker:
        set only ``OzelAlan1`` on the UrunKarti and flip
        ``OzelAlan1Guncelle=True`` on UrunKartiAyar. Every other
        ``*Guncelle`` flag defaults to False so no other field is touched.
        """

        def _do() -> Any:
            karti = client.urun_factory.UrunKarti(
                ID=urun_karti_id,
                OzelAlan1=yeni_oa1,
            )
            ayar = client.urun_factory.UrunKartiAyar(
                OzelAlan1Guncelle=True,
            )
            return client.urun.UrunKartiGuncelle(
                UyeKodu=client.uye_kodu,
                urunKarti=karti,
                urunKartiAyar=ayar,
            )

        await asyncio.to_thread(_do)

    def _abort(
        self,
        out_results: list[dict[str, Any]],
        updated: int,
        errors: int,
        skip_has_oa1: int,
        skip_no_sku: int,
        skip_noop: int,
        skip_same: int,
        dry_run: bool,
    ) -> dict[str, Any]:
        last_errors = [r.get("error", "?") for r in out_results[-3:] if r.get("status") == "error"]
        raise NodeError(
            "",
            self.type_id,
            f"Aborted: consecutive errors exceeded threshold. "
            f"updated={updated}, errors={errors}, "
            f"skip_has_oa1={skip_has_oa1}, skip_no_sku={skip_no_sku}, "
            f"skip_noop={skip_noop}, skip_same={skip_same}. "
            f"Last: {last_errors}",
        )
