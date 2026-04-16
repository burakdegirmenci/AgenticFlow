"""Batch stock update by barcode — matches Excel barcodes to Ticimax variations.

Flow:
1. Receives items with {Barkod, Miktar} from upstream (e.g. input.excel_read)
2. Fetches ALL active products from Ticimax to build a Barkod → VaryasyonID map
3. For each Excel row, finds the matching variation
4. Calls StokAdediGuncelle with the matched VaryasyonID + new StokAdedi
5. dry_run mode: skips the API call, just reports what WOULD change

The Barkod→VaryasyonID lookup is done in-memory because Ticimax has no
"search by barcode" API. We fetch all active products once (paginated)
and build a dict. For stores with <50K products this is fast enough;
larger stores should use a cached version (future optimization).
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.engine.context import ExecutionContext
from app.engine.errors import NodeError
from app.engine.node_base import BaseNode
from app.logging_config import get_logger
from app.nodes import register
from app.nodes.ai._common import _get_path, flatten_inputs
from app.services.ticimax_service import TicimaxService

logger = get_logger("agenticflow.nodes.ticimax.stok_guncelle_by_barkod")


def _build_barkod_map(client: Any) -> dict[str, dict[str, Any]]:
    """Fetch all active products and build Barkod → {VaryasyonID, StokKodu, StokAdedi} map."""
    barkod_map: dict[str, dict[str, Any]] = {}
    page_size = 500
    offset = 0
    total_fetched = 0

    while True:
        filtre = client.urun_factory.UrunFiltre(
            UrunKartiID=-1,
            MarkaID=-1,
            KategoriID=-1,
            TedarikciID=-1,
            Aktif=1,
            StokKodu="",
        )
        sayfalama = client.urun_factory.UrunSayfalama(
            BaslangicIndex=offset,
            KayitSayisi=page_size,
            SiralamaDegeri="id",
            SiralamaYonu="Asc",
        )
        urunler = client.urun.SelectUrun(UyeKodu=client.uye_kodu, f=filtre, s=sayfalama)
        if not urunler:
            break

        from ticimax_client import serialize_zeep_object  # type: ignore[import-not-found]

        batch = [
            serialize_zeep_object(u) for u in (urunler if isinstance(urunler, list) else [urunler])
        ]
        for urun in batch:
            v = urun.get("Varyasyonlar")
            if not isinstance(v, dict):
                continue
            vlist = v.get("Varyasyon", [])
            if not isinstance(vlist, list):
                vlist = [vlist]
            for var in vlist:
                if not isinstance(var, dict):
                    continue
                barkod = str(var.get("Barkod") or "").strip()
                var_id = var.get("ID")
                if barkod and var_id:
                    barkod_map[barkod] = {
                        "VaryasyonID": var_id,
                        "StokKodu": var.get("StokKodu"),
                        "MevcutStok": var.get("StokAdedi"),
                        "UrunAdi": urun.get("UrunAdi"),
                    }
        total_fetched += len(batch)
        if len(batch) < page_size:
            break
        offset += page_size

    logger.info(
        "barkod_map_built",
        extra={"total_products": total_fetched, "total_barcodes": len(barkod_map)},
    )
    return barkod_map


@register
class StokGuncelleByBarkodNode(BaseNode):
    type_id = "ticimax.stok_guncelle_by_barkod"
    category = "ticimax"
    display_name = "Stok Güncelle (Barkod ile)"
    description = (
        "Excel'den gelen Barkod+Miktar listesini Ticimax varyasyonlarıyla "
        "eşler ve stok adedini toplu günceller. dry_run ile önce kontrol edin."
    )
    icon = "package-check"
    color = "#059669"

    input_schema = {
        "type": "object",
        "properties": {
            "items": {"type": "array", "description": "Barkod+Miktar içeren satırlar"},
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "matched": {"type": "integer"},
            "not_found": {"type": "integer"},
            "updated": {"type": "integer"},
            "errors": {"type": "integer"},
            "dry_run": {"type": "boolean"},
            "results": {"type": "array"},
        },
    }

    config_schema = {
        "type": "object",
        "properties": {
            "barkod_field": {
                "type": "string",
                "title": "Barkod Alan Adı",
                "description": "Excel'deki barkod kolonunun eşlenmiş adı.",
                "default": "Barkod",
            },
            "miktar_field": {
                "type": "string",
                "title": "Miktar Alan Adı",
                "description": "Excel'deki stok miktarı kolonunun eşlenmiş adı.",
                "default": "Miktar",
            },
            "dry_run": {
                "type": "boolean",
                "title": "Sadece Önizleme (Dry Run)",
                "description": "true = Ticimax'a yazma, sadece eşleşme raporla.",
                "default": True,
            },
            "batch_size": {
                "type": "integer",
                "title": "Batch Boyutu",
                "description": "Kaç varyasyonu tek API çağrısında güncelle.",
                "default": 50,
                "minimum": 1,
                "maximum": 500,
            },
        },
    }

    async def execute(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        barkod_field = str(config.get("barkod_field", "Barkod"))
        miktar_field = str(config.get("miktar_field", "Miktar"))
        dry_run = bool(config.get("dry_run", True))
        batch_size = int(config.get("batch_size", 50))

        # Resolve items from upstream (excel_read output)
        merged = flatten_inputs(inputs)
        items_raw = _get_path(merged, "items")
        if items_raw is None:
            # Try common parent output shapes
            for v in merged.values():
                if isinstance(v, dict) and "items" in v:
                    items_raw = v["items"]
                    break

        if not isinstance(items_raw, list):
            raise NodeError("", self.type_id, "Upstream 'items' listesi bulunamadı.")

        items: list[dict[str, Any]] = [i for i in items_raw if isinstance(i, dict)]
        if not items:
            return {
                "matched": 0,
                "not_found": 0,
                "updated": 0,
                "errors": 0,
                "dry_run": dry_run,
                "results": [],
            }

        # Build Barkod → VaryasyonID map from Ticimax
        client = TicimaxService.get_client(context.site)
        barkod_map = await asyncio.to_thread(_build_barkod_map, client)

        # Match Excel rows
        results: list[dict[str, Any]] = []
        matched_updates: list[dict[str, Any]] = []
        not_found_count = 0

        for i, row in enumerate(items):
            barkod = str(row.get(barkod_field, "")).strip()
            miktar_raw = row.get(miktar_field)
            try:
                miktar = int(float(miktar_raw)) if miktar_raw is not None else None
            except (ValueError, TypeError):
                miktar = None

            if not barkod:
                results.append({"index": i, "status": "skip", "reason": "barkod_empty"})
                continue

            if miktar is None:
                results.append(
                    {"index": i, "barkod": barkod, "status": "skip", "reason": "miktar_invalid"}
                )
                continue

            info = barkod_map.get(barkod)
            if not info:
                not_found_count += 1
                results.append({"index": i, "barkod": barkod, "status": "not_found"})
                continue

            matched_updates.append(
                {
                    "VaryasyonID": info["VaryasyonID"],
                    "Barkod": barkod,
                    "YeniStok": miktar,
                    "MevcutStok": info["MevcutStok"],
                    "StokKodu": info["StokKodu"],
                    "UrunAdi": info["UrunAdi"],
                }
            )
            results.append(
                {
                    "index": i,
                    "barkod": barkod,
                    "varyasyon_id": info["VaryasyonID"],
                    "stok_kodu": info["StokKodu"],
                    "mevcut_stok": info["MevcutStok"],
                    "yeni_stok": miktar,
                    "status": "would_update" if dry_run else "pending",
                }
            )

        updated_count = 0
        error_count = 0

        if not dry_run and matched_updates:
            # Batch update via StokAdediGuncelle
            for batch_start in range(0, len(matched_updates), batch_size):
                batch = matched_updates[batch_start : batch_start + batch_size]
                try:

                    def _do_update(b: list[dict[str, Any]] = batch) -> str:
                        urunler = []
                        for u in b:
                            var_obj = client.urun_factory.Varyasyon(
                                ID=u["VaryasyonID"],
                                StokAdedi=u["YeniStok"],
                            )
                            urunler.append(var_obj)
                        result = client.urun.StokAdediGuncelle(
                            UyeKodu=client.uye_kodu, urunler=urunler
                        )
                        return str(result) if result else "OK"

                    await asyncio.to_thread(_do_update)
                    updated_count += len(batch)
                    # Mark results as updated
                    for u in batch:
                        for r in results:
                            if r.get("varyasyon_id") == u["VaryasyonID"]:
                                r["status"] = "updated"
                except Exception as e:
                    error_count += len(batch)
                    logger.error(
                        "stok_batch_error", extra={"error": str(e), "batch_size": len(batch)}
                    )
                    for u in batch:
                        for r in results:
                            if r.get("varyasyon_id") == u["VaryasyonID"]:
                                r["status"] = "error"
                                r["error"] = str(e)[:200]

        return {
            "matched": len(matched_updates),
            "not_found": not_found_count,
            "updated": updated_count,
            "errors": error_count,
            "dry_run": dry_run,
            "total_items": len(items),
            "total_barcodes_in_ticimax": len(barkod_map),
            "results": results[:100],  # cap for display
        }
