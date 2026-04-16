"""Batch stock update by barcode — uses SelectVaryasyon for direct lookup.

For each Excel row (Barkod + Miktar):
1. SelectVaryasyon(barkod=X) → finds the VaryasyonID directly (1 SOAP call)
2. Collects all matched {VaryasyonID, StokAdedi} pairs
3. StokAdediGuncelle in one batch call

No full-catalog crawl, no cache file, no SQLite index. Each barcode
lookup is a single targeted SOAP call (~0.5-1s). For 100 rows this is
~60s; for 3600 rows it would be ~30-60min one-by-one. So we batch
the lookups: SelectVaryasyon(kayit_sayisi=1000) without barcode filter
fetches ALL variations in pages — much faster than N individual calls
when N > ~200.

Strategy selection:
- N ≤ 200 items: individual SelectVaryasyon(barkod=X) calls — fast + targeted
- N > 200 items: paginated SelectVaryasyon(all) → build in-memory map — one-time cost

dry_run mode: skips StokAdediGuncelle, reports what WOULD change.
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

_INDIVIDUAL_LOOKUP_THRESHOLD = 200


def _lookup_individual(client: Any, barkodlar: list[str]) -> dict[str, dict[str, Any]]:
    """Lookup each barcode individually via SelectVaryasyon(barkod=X)."""
    result: dict[str, dict[str, Any]] = {}
    from ticimax_client import serialize_zeep_object  # type: ignore[import-not-found]

    for i, barkod in enumerate(barkodlar):
        if not barkod:
            continue
        try:
            filtre = client.urun_factory.SelectVaryasyonFiltre(
                UrunKartiID=-1,
                Barkod=barkod,
                StokKodu="",
            )
            sayfalama = client.urun_factory.SelectVaryasyonSayfalama(
                BaslangicIndex=0,
                KayitSayisi=1,
                SiralamaDegeri="id",
                SiralamaYonu="Desc",
            )
            ayar = client.urun_factory.SelectVaryasyonAyar()
            varyasyonlar = client.urun.SelectVaryasyon(
                UyeKodu=client.uye_kodu,
                f=filtre,
                s=sayfalama,
                varyasyonAyar=ayar,
            )
            if varyasyonlar:
                vlist = varyasyonlar if isinstance(varyasyonlar, list) else [varyasyonlar]
                for v in vlist:
                    data = serialize_zeep_object(v)
                    var_id = data.get("ID")
                    if var_id:
                        result[barkod] = {
                            "VaryasyonID": var_id,
                            "StokKodu": data.get("StokKodu"),
                            "MevcutStok": data.get("StokAdedi"),
                        }
                        break  # first match is enough
        except Exception as e:
            logger.warning("barkod_lookup_error", extra={"barkod": barkod, "error": str(e)[:100]})

        if (i + 1) % 50 == 0:
            logger.info("barkod_lookup_progress", extra={"done": i + 1, "total": len(barkodlar)})

    return result


def _lookup_bulk(client: Any) -> dict[str, dict[str, Any]]:
    """Fetch ALL variations paginated, build barkod map in memory."""
    result: dict[str, dict[str, Any]] = {}
    page_size = 1000
    offset = 0
    from ticimax_client import serialize_zeep_object  # type: ignore[import-not-found]

    while True:
        filtre = client.urun_factory.SelectVaryasyonFiltre(
            UrunKartiID=-1,
            Barkod="",
            StokKodu="",
        )
        sayfalama = client.urun_factory.SelectVaryasyonSayfalama(
            BaslangicIndex=offset,
            KayitSayisi=page_size,
            SiralamaDegeri="id",
            SiralamaYonu="Asc",
        )
        ayar = client.urun_factory.SelectVaryasyonAyar()
        varyasyonlar = client.urun.SelectVaryasyon(
            UyeKodu=client.uye_kodu,
            f=filtre,
            s=sayfalama,
            varyasyonAyar=ayar,
        )
        if not varyasyonlar:
            break

        batch = varyasyonlar if isinstance(varyasyonlar, list) else [varyasyonlar]
        for v in batch:
            data = serialize_zeep_object(v)
            barkod = str(data.get("Barkod") or "").strip()
            var_id = data.get("ID")
            if barkod and var_id:
                result[barkod] = {
                    "VaryasyonID": var_id,
                    "StokKodu": data.get("StokKodu"),
                    "MevcutStok": data.get("StokAdedi"),
                }

        logger.info(
            "bulk_varyasyon_progress",
            extra={"fetched": offset + len(batch), "barcodes": len(result)},
        )
        if len(batch) < page_size:
            break
        offset += page_size

    return result


@register
class StokGuncelleByBarkodNode(BaseNode):
    type_id = "ticimax.stok_guncelle_by_barkod"
    category = "ticimax"
    display_name = "Stok Güncelle (Barkod ile)"
    description = (
        "Excel'den gelen Barkod+Miktar listesini Ticimax varyasyonlarıyla "
        "eşler ve stok adedini toplu günceller. Küçük listeler için barkod "
        "bazlı tekil arama, büyük listeler için toplu çekim kullanır."
    )
    icon = "package-check"
    color = "#059669"

    input_schema = {
        "type": "object",
        "properties": {
            "items": {"type": "array"},
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "matched": {"type": "integer"},
            "not_found": {"type": "integer"},
            "updated": {"type": "integer"},
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
                "default": "Barkod",
            },
            "miktar_field": {
                "type": "string",
                "title": "Miktar Alan Adı",
                "default": "Miktar",
            },
            "dry_run": {
                "type": "boolean",
                "title": "Sadece Önizleme (Dry Run)",
                "description": "true = yazma, sadece raporla.",
                "default": True,
            },
            "batch_size": {
                "type": "integer",
                "title": "Güncelleme Batch Boyutu",
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

        # Resolve items
        merged = flatten_inputs(inputs)
        items_raw = _get_path(merged, "items")
        if items_raw is None:
            for v in merged.values():
                if isinstance(v, dict) and "items" in v:
                    items_raw = v["items"]
                    break

        if not isinstance(items_raw, list):
            raise NodeError("", self.type_id, "Upstream 'items' bulunamadı.")

        items: list[dict[str, Any]] = [i for i in items_raw if isinstance(i, dict)]
        if not items:
            return {"matched": 0, "not_found": 0, "updated": 0, "dry_run": dry_run, "results": []}

        # Extract unique barcodes
        barkodlar = list(
            {str(row.get(barkod_field, "")).strip() for row in items if row.get(barkod_field)}
        )

        # Choose strategy
        client = TicimaxService.get_client(context.site)
        if len(barkodlar) <= _INDIVIDUAL_LOOKUP_THRESHOLD:
            logger.info(
                "lookup_strategy", extra={"strategy": "individual", "barcodes": len(barkodlar)}
            )
            barkod_map = await asyncio.to_thread(_lookup_individual, client, barkodlar)
        else:
            logger.info("lookup_strategy", extra={"strategy": "bulk", "barcodes": len(barkodlar)})
            barkod_map = await asyncio.to_thread(_lookup_bulk, client)

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
                    "StokKodu": info.get("StokKodu"),
                }
            )
            results.append(
                {
                    "index": i,
                    "barkod": barkod,
                    "varyasyon_id": info["VaryasyonID"],
                    "stok_kodu": info.get("StokKodu"),
                    "mevcut_stok": info["MevcutStok"],
                    "yeni_stok": miktar,
                    "status": "would_update" if dry_run else "pending",
                }
            )

        updated_count = 0
        error_count = 0

        if not dry_run and matched_updates:
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
                            UyeKodu=client.uye_kodu,
                            urunler=urunler,
                        )
                        return str(result) if result else "OK"

                    await asyncio.to_thread(_do_update)
                    updated_count += len(batch)
                    for u in batch:
                        for r in results:
                            if r.get("varyasyon_id") == u["VaryasyonID"]:
                                r["status"] = "updated"
                except Exception as e:
                    error_count += len(batch)
                    logger.error(
                        "stok_batch_error", extra={"error": str(e), "batch_size": len(batch)}
                    )

        return {
            "matched": len(matched_updates),
            "not_found": not_found_count,
            "updated": updated_count,
            "errors": error_count,
            "dry_run": dry_run,
            "total_items": len(items),
            "lookup_strategy": "individual"
            if len(barkodlar) <= _INDIVIDUAL_LOOKUP_THRESHOLD
            else "bulk",
            "unique_barcodes": len(barkodlar),
            "results": results[:200],
        }
