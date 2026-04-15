"""Batch update node: write the generated Aciklama back to Ticimax.

Consumes the results array produced by ``ai.vision_batch`` and for each
successful item calls ``UrunKartiGuncelle`` with ``Aciklama`` +
``AciklamaGuncelle=True``. Explicitly does NOT touch ``OnYazi`` or
any other product field.

Abort policy: if ``abort_on_consecutive_errors`` updates fail in a row
the node raises NodeError (the workflow stops). Counter resets on
every successful update.

Supports ``dry_run`` config — when true, nothing is sent to Ticimax
but the node still iterates and returns what it would have written.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.engine.context import ExecutionContext
from app.engine.errors import NodeError
from app.engine.node_base import BaseNode
from app.nodes import register
from app.nodes.ai._common import _get_path, flatten_inputs
from app.services.ticimax_service import TicimaxService


@register
class UrunUpdateAciklamaBatchNode(BaseNode):
    type_id = "ticimax.urun.update_aciklama_batch"
    category = "ticimax"
    display_name = "Ürün Açıklaması Güncelle (Batch)"
    description = (
        "ai.vision_batch'ten gelen sonuç listesindeki her ürün için "
        "Ticimax'ta Aciklama alanını günceller. Ön Yazı alanına dokunmaz. "
        "Üst üste N hata olursa flow'u durdurur."
    )
    icon = "edit-3"
    color = "#0ea5e9"

    input_schema = {
        "type": "object",
        "properties": {"results": {"type": "array"}},
    }

    output_schema = {
        "type": "object",
        "properties": {
            "updated_count": {"type": "integer"},
            "error_count": {"type": "integer"},
            "skipped_count": {"type": "integer"},
            "dry_run": {"type": "boolean"},
            "aborted": {"type": "boolean"},
            "results": {"type": "array"},
        },
    }

    config_schema = {
        "type": "object",
        "properties": {
            "results_path": {
                "type": "string",
                "title": "Sonuç Listesi Path'i",
                "description": (
                    "Flattened input içinde sonuç dizisinin yolu. "
                    "Boş = parent'tan 'results' alanını bul."
                ),
                "default": "results",
            },
            "id_field": {
                "type": "string",
                "title": "ID Alanı (item içinde)",
                "default": "urun_karti_id",
            },
            "aciklama_field": {
                "type": "string",
                "title": "Açıklama Alanı (item içinde)",
                "default": "aciklama",
            },
            "success_field": {
                "type": "string",
                "title": "Başarı Alanı (item içinde)",
                "description": "Bu alan False ise item atlanır",
                "default": "success",
            },
            "dry_run": {
                "type": "boolean",
                "title": "Dry Run (yazma, sadece log)",
                "default": False,
            },
            "item_delay_ms": {
                "type": "integer",
                "title": "Öğeler Arası Bekleme (ms)",
                "default": 250,
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
        "required": ["id_field", "aciklama_field"],
    }

    async def execute(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        results_path = str(config.get("results_path", "results")).strip() or "results"
        id_field = str(config.get("id_field", "urun_karti_id"))
        aciklama_field = str(config.get("aciklama_field", "aciklama"))
        success_field = str(config.get("success_field", "success")) or ""
        dry_run = bool(config.get("dry_run", False))
        delay_sec = int(config.get("item_delay_ms", 250)) / 1000.0
        abort_threshold = int(config.get("abort_on_consecutive_errors", 3))

        merged = flatten_inputs(inputs)
        raw = _get_path(merged, results_path)
        if raw is None and "results" in merged:
            raw = merged["results"]

        if not isinstance(raw, list):
            raise NodeError(
                "",
                self.type_id,
                f"results_path '{results_path}' did not resolve to a list "
                f"(got {type(raw).__name__})",
            )

        items: list[dict[str, Any]] = [r for r in raw if isinstance(r, dict)]

        if not items:
            return {
                "updated_count": 0,
                "error_count": 0,
                "skipped_count": 0,
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
        skipped = 0
        consecutive_errors = 0

        for idx, item in enumerate(items):
            urun_karti_id = item.get(id_field)
            aciklama = item.get(aciklama_field)

            # Skip items flagged as unsuccessful upstream
            if success_field and success_field in item and not item.get(success_field):
                skipped += 1
                out_results.append(
                    {
                        "index": idx,
                        "urun_karti_id": urun_karti_id,
                        "status": "skipped",
                        "reason": f"upstream {success_field}=False",
                    }
                )
                continue

            if not urun_karti_id:
                errors += 1
                consecutive_errors += 1
                out_results.append(
                    {
                        "index": idx,
                        "urun_karti_id": urun_karti_id,
                        "status": "error",
                        "error": f"missing '{id_field}'",
                    }
                )
                if consecutive_errors >= abort_threshold:
                    return self._abort(out_results, updated, errors, skipped, dry_run)
                continue

            if not aciklama or not str(aciklama).strip():
                errors += 1
                consecutive_errors += 1
                out_results.append(
                    {
                        "index": idx,
                        "urun_karti_id": urun_karti_id,
                        "status": "error",
                        "error": f"empty '{aciklama_field}'",
                    }
                )
                if consecutive_errors >= abort_threshold:
                    return self._abort(out_results, updated, errors, skipped, dry_run)
                continue

            if dry_run:
                updated += 1
                consecutive_errors = 0
                out_results.append(
                    {
                        "index": idx,
                        "urun_karti_id": urun_karti_id,
                        "status": "dry_run",
                        "aciklama_preview": str(aciklama)[:200],
                    }
                )
            else:
                try:
                    await self._update_one(client, int(urun_karti_id), str(aciklama))
                    updated += 1
                    consecutive_errors = 0
                    out_results.append(
                        {
                            "index": idx,
                            "urun_karti_id": urun_karti_id,
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
                            "status": "error",
                            "error": str(e)[:500],
                        }
                    )
                    if consecutive_errors >= abort_threshold:
                        return self._abort(out_results, updated, errors, skipped, dry_run)

            if delay_sec > 0 and idx < len(items) - 1:
                await asyncio.sleep(delay_sec)

        return {
            "updated_count": updated,
            "error_count": errors,
            "skipped_count": skipped,
            "dry_run": dry_run,
            "aborted": False,
            "results": out_results,
        }

    # ------------------------------------------------------------------
    async def _update_one(self, client: Any, urun_karti_id: int, aciklama: str) -> None:
        """Single UrunKartiGuncelle call — runs the blocking SOAP in a thread."""

        def _do() -> Any:
            karti = client.urun_factory.UrunKarti(
                ID=urun_karti_id,
                Aciklama=aciklama,
            )
            ayar = client.urun_factory.UrunKartiAyar(
                AciklamaGuncelle=True,
                # Explicitly disable OnYazi updates to be safe.
                OnYaziGuncelle=False,
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
        skipped: int,
        dry_run: bool,
    ) -> dict[str, Any]:
        last_errors = [r.get("error", "?") for r in out_results[-3:] if r.get("status") == "error"]
        raise NodeError(
            "",
            self.type_id,
            f"Aborted: consecutive errors exceeded threshold. "
            f"updated={updated}, errors={errors}, skipped={skipped}. "
            f"Last: {last_errors}",
        )
