"""Batch node: set SiparisDurum for orders coming from ``siparis.select``.

Consumes the ``siparisler`` list produced by ``ticimax.siparis.select`` and
for each order:

  1. Validates the order has an ID.
  2. Optionally client-side filters by ``OdemeTipi`` in
     ``Odemeler.WebSiparisOdeme[].OdemeTipi`` — Ticimax's server-side
     ``OdemeTipi`` filter on ``WebSiparisFiltre`` is not reliable, so we do
     the check here. Upstream node must set ``odeme_getir=True`` for this
     filter to work.
  3. Optionally requires the payment record to have ``Onaylandi=1``.
  4. Calls ``SetSiparisDurum`` with the configured new status (default
     ``Onaylandi``) via zeep in a worker thread.

Supports ``dry_run`` — when True nothing is sent to Ticimax but the node
iterates and reports what it would have changed. Abort policy: if
``abort_on_consecutive_errors`` updates fail in a row the node raises
NodeError and the workflow stops. Counter resets on every success.

Skip statuses:
  - ``skip_no_id``: order has no ID → error
  - ``skip_no_payment``: ``Odemeler`` missing / empty AND ``OdenenTutar``
    indicates no money received — genuinely unpaid
  - ``skip_wrong_odeme_tipi``: no nested payment matches the required tip
  - ``skip_not_approved``: all matching payments have ``Onaylandi != 1``
  - ``skip_no_kargo_takip_no``: ``require_kargo_takip_no`` is True but the
    order has no ``KargoTakipNo`` — used by the cargo-dispatch workflow to
    skip orders that haven't been shipped yet.

When updating to ``KargoyaVerildi`` with ``require_kargo_takip_no=True``,
the node passes the order's ``KargoTakipNo`` and ``KargoTakipLink``
through to the ``SetSiparisDurumRequest`` so Ticimax stores them on the
status transition (this also triggers the customer shipping-notification
email if ``mail_bilgilendir=True``).

Ticimax quirk: When ``SelectSiparis`` is called with many orders at
once, some orders come back with empty ``Odemeler`` even though
``OdemeGetir=True`` is set. The same order queried individually returns
the full payment list. ``OdenenTutar`` is also flaky in batch responses
(returns 0 even for genuinely paid orders). We work around this by
re-fetching any order where ``Odemeler`` is missing — the individual
query is the source of truth. See ``refetch_missing_odemeler``.
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


def _extract_odemeler(siparis: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the list of ``WebSiparisOdeme`` dicts, or ``[]``.

    Handles both list and single-dict zeep responses.
    """
    odemeler = siparis.get("Odemeler")
    if not isinstance(odemeler, dict):
        return []
    lst = odemeler.get("WebSiparisOdeme")
    if lst is None:
        return []
    if not isinstance(lst, list):
        lst = [lst]
    return [p for p in lst if isinstance(p, dict)]


@register
class SetSiparisDurumBatchNode(BaseNode):
    type_id = "ticimax.siparis.set_durum_batch"
    category = "ticimax"
    display_name = "Sipariş Durum Güncelle (Batch)"
    description = (
        "Upstream'den gelen sipariş listesindeki her sipariş için "
        "SetSiparisDurum çağırır. Opsiyonel olarak client-side OdemeTipi "
        "filtresi ile sadece belirli ödeme tiplerinin siparişlerini "
        "günceller (Odemeler.WebSiparisOdeme[] içine bakar)."
    )
    icon = "check-circle"
    color = "#10b981"

    input_schema = {
        "type": "object",
        "properties": {"siparisler": {"type": "array"}},
    }

    output_schema = {
        "type": "object",
        "properties": {
            "updated_count": {"type": "integer"},
            "error_count": {"type": "integer"},
            "skipped_count": {"type": "integer"},
            "skip_no_payment": {"type": "integer"},
            "skip_wrong_odeme_tipi": {"type": "integer"},
            "skip_not_approved": {"type": "integer"},
            "skip_no_kargo_takip_no": {"type": "integer"},
            "refetch_count": {"type": "integer"},
            "dry_run": {"type": "boolean"},
            "aborted": {"type": "boolean"},
            "results": {"type": "array"},
        },
    }

    config_schema = {
        "type": "object",
        "properties": {
            "siparisler_path": {
                "type": "string",
                "title": "Sipariş Listesi Path",
                "description": (
                    "Flattened input içinde sipariş dizisinin yolu. "
                    "Boş = 'siparisler' alanından oku."
                ),
                "default": "siparisler",
            },
            "yeni_durum": {
                "type": "string",
                "title": "Yeni Sipariş Durumu",
                "description": "SetSiparisDurum API'sine gönderilecek durum.",
                "default": "Onaylandi",
                "enum": [
                    "SiparisAlindi",
                    "OnayBekliyor",
                    "Onaylandi",
                    "OdemeBekliyor",
                    "Paketleniyor",
                    "TedarikEdiliyor",
                    "KargoyaVerildi",
                    "TeslimEdildi",
                    "Iptal",
                    "Iade",
                ],
            },
            "mail_bilgilendir": {
                "type": "boolean",
                "title": "Müşteriye Mail Gönder",
                "description": (
                    "True ise durum değişikliği e-postası müşteriye otomatik gönderilir."
                ),
                "default": False,
            },
            "require_odeme_tipi_in": {
                "type": "array",
                "title": "Gerekli Ödeme Tipleri (liste)",
                "description": (
                    "Boş liste = ödeme tipi filtresi uygulanmaz. Örnek: "
                    "[0] = sadece KrediKarti; [0,3] = KrediKarti + "
                    "KapidaKrediKarti. Upstream node'da odeme_getir=True "
                    "olmalı."
                ),
                "items": {"type": "integer"},
                "default": [0],
            },
            "require_odeme_onayli": {
                "type": "boolean",
                "title": "Ödemenin Onaylanmış Olması Gerekli",
                "description": (
                    "True ise sadece Odemeler.WebSiparisOdeme[].Onaylandi "
                    "= 1 olan siparişler güncellenir."
                ),
                "default": True,
            },
            "refetch_missing_odemeler": {
                "type": "boolean",
                "title": "Eksik Ödeme Bilgisi Olanları Yeniden Sorgula",
                "description": (
                    "Ticimax bazen batch fetch'te Odemeler alanını boş "
                    "dönüyor (OdenenTutar da flaky). True ise Odemeler "
                    "boş olan her sipariş için tekil SOAP sorgusu yapılır "
                    "— bu gerçek ödeme durumunu ortaya çıkarır. 100 sipariş "
                    "için ~5-10sn ek süre."
                ),
                "default": True,
            },
            "require_kargo_takip_no": {
                "type": "boolean",
                "title": "Kargo Takip Numarası Gerekli",
                "description": (
                    "True ise sadece KargoTakipNo dolu olan siparişler "
                    "güncellenir (kargoya verildi iş akışı için). "
                    "Güncellemede KargoTakipNo + KargoTakipLink "
                    "SetSiparisDurumRequest'e pass-through edilir."
                ),
                "default": False,
            },
            "dry_run": {
                "type": "boolean",
                "title": "Dry Run (yazma, sadece log)",
                "default": True,
            },
            "max_updates": {
                "type": "integer",
                "title": "Maksimum Güncelleme Sayısı",
                "description": (
                    "0 = limitsiz. Eşleşen sipariş sayısı bu limite "
                    "ulaşınca node durur — güvenli test için ideal "
                    "(ör. 1, 5, 10)."
                ),
                "default": 0,
                "minimum": 0,
                "maximum": 10000,
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
                "default": 5,
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
        path = str(config.get("siparisler_path", "siparisler")).strip() or "siparisler"
        yeni_durum = (config.get("yeni_durum") or "Onaylandi").strip() or "Onaylandi"
        mail_bilgilendir = bool(config.get("mail_bilgilendir", False))
        require_tipler_raw = config.get("require_odeme_tipi_in")
        if require_tipler_raw is None:
            require_tipler: set[int] = {0}
        else:
            require_tipler = {
                int(x) for x in require_tipler_raw if x is not None and str(x).strip() != ""
            }
        require_onayli = bool(config.get("require_odeme_onayli", True))
        refetch_missing = bool(config.get("refetch_missing_odemeler", True))
        require_kargo_takip_no = bool(config.get("require_kargo_takip_no", False))
        dry_run = bool(config.get("dry_run", True))
        max_updates = int(config.get("max_updates", 0) or 0)
        delay_sec = int(config.get("item_delay_ms", 150)) / 1000.0
        abort_threshold = int(config.get("abort_on_consecutive_errors", 5))

        merged = flatten_inputs(inputs)
        raw = _get_path(merged, path)
        if raw is None and "siparisler" in merged:
            raw = merged["siparisler"]

        if not isinstance(raw, list):
            raise NodeError(
                "",
                self.type_id,
                f"siparisler_path '{path}' did not resolve to a list (got {type(raw).__name__})",
            )

        items: list[dict[str, Any]] = [s for s in raw if isinstance(s, dict)]

        if not items:
            return {
                "updated_count": 0,
                "error_count": 0,
                "skipped_count": 0,
                "skip_no_payment": 0,
                "skip_wrong_odeme_tipi": 0,
                "skip_not_approved": 0,
                "skip_no_kargo_takip_no": 0,
                "refetch_count": 0,
                "dry_run": dry_run,
                "aborted": False,
                "results": [],
            }

        # Client is needed when we update (!dry_run) OR when we refetch
        # missing Odemeler (which queries Ticimax even in dry-run mode).
        client = None
        needs_client = (not dry_run) or (refetch_missing and bool(require_tipler))
        if needs_client:
            client = TicimaxService.get_client(context.site)

        out_results: list[dict[str, Any]] = []
        updated = 0
        errors = 0
        skip_no_payment = 0
        skip_wrong_odeme_tipi = 0
        skip_not_approved = 0
        skip_no_kargo_takip_no = 0
        refetch_total = 0  # how many refetch calls were made (success or fail)
        consecutive_errors = 0

        for idx, siparis in enumerate(items):
            siparis_id = siparis.get("ID") or siparis.get("SiparisID")
            siparis_no = siparis.get("SiparisNo") or ""
            adi = (siparis.get("AdiSoyadi") or "").strip()
            mevcut_durum = siparis.get("SiparisDurumu") or siparis.get("Durum")
            refetched = False  # for marker propagation across branches
            refetch_failed = False
            refetch_err_msg = ""

            if not siparis_id:
                errors += 1
                consecutive_errors += 1
                out_results.append(
                    {
                        "index": idx,
                        "siparis_id": None,
                        "siparis_no": siparis_no,
                        "status": "error",
                        "error": "missing ID / SiparisID",
                    }
                )
                if consecutive_errors >= abort_threshold:
                    return self._abort(
                        out_results,
                        updated,
                        errors,
                        skip_no_payment,
                        skip_wrong_odeme_tipi,
                        skip_not_approved,
                        dry_run,
                    )
                continue

            # ---- Client-side payment filter ---------------------------
            if require_tipler:
                odemeler = _extract_odemeler(siparis)
                if not odemeler and refetch_missing and client is not None:
                    # Ticimax batch fetch returns empty Odemeler for some
                    # orders even with OdemeGetir=True (and OdenenTutar is
                    # also unreliable as a signal). The individual query
                    # is the source of truth, so we always refetch when
                    # Odemeler is missing.
                    refetch_total += 1
                    try:
                        refetched_siparis = await self._refetch_one(client, int(siparis_id))
                        if refetched_siparis:
                            odemeler = _extract_odemeler(refetched_siparis)
                            refetched = True
                    except Exception as e:
                        # Refetch failure is non-fatal; fall through and
                        # record a refetch_error marker.
                        refetch_failed = True
                        refetch_err_msg = str(e)[:200]

                if not odemeler:
                    skip_no_payment += 1
                    marker: dict[str, Any] = {}
                    if refetched:
                        marker["refetched"] = True
                    if refetch_failed:
                        marker["refetch_error"] = refetch_err_msg
                    out_results.append(
                        {
                            "index": idx,
                            "siparis_id": siparis_id,
                            "siparis_no": siparis_no,
                            "adi": adi,
                            "mevcut_durum": mevcut_durum,
                            "status": "skip_no_payment",
                            **marker,
                        }
                    )
                    continue

                matching_tip = [p for p in odemeler if p.get("OdemeTipi") in require_tipler]
                if not matching_tip:
                    skip_wrong_odeme_tipi += 1
                    tipler_gorulen = [p.get("OdemeTipi") for p in odemeler]
                    out_results.append(
                        {
                            "index": idx,
                            "siparis_id": siparis_id,
                            "siparis_no": siparis_no,
                            "adi": adi,
                            "mevcut_durum": mevcut_durum,
                            "gorulen_tipler": tipler_gorulen,
                            "status": "skip_wrong_odeme_tipi",
                            **({"refetched": True} if refetched else {}),
                        }
                    )
                    continue

                if require_onayli:
                    onayli = [p for p in matching_tip if p.get("Onaylandi") == 1]
                    if not onayli:
                        skip_not_approved += 1
                        out_results.append(
                            {
                                "index": idx,
                                "siparis_id": siparis_id,
                                "siparis_no": siparis_no,
                                "adi": adi,
                                "mevcut_durum": mevcut_durum,
                                "status": "skip_not_approved",
                                **({"refetched": True} if refetched else {}),
                            }
                        )
                        continue

            # ---- Kargo takip no filter (cargo-dispatch workflow) -----
            kargo_takip_no: str | None = None
            kargo_takip_link: str | None = None
            if require_kargo_takip_no:
                ktn = siparis.get("KargoTakipNo")
                ktl = siparis.get("KargoTakipLink")
                kargo_takip_no = str(ktn).strip() if ktn else ""
                kargo_takip_link = str(ktl).strip() if ktl else ""
                if not kargo_takip_no:
                    skip_no_kargo_takip_no += 1
                    out_results.append(
                        {
                            "index": idx,
                            "siparis_id": siparis_id,
                            "siparis_no": siparis_no,
                            "adi": adi,
                            "mevcut_durum": mevcut_durum,
                            "status": "skip_no_kargo_takip_no",
                            **({"refetched": True} if refetched else {}),
                        }
                    )
                    continue

            # Extra fields we may want to echo into the result record.
            kargo_marker: dict[str, Any] = {}
            if kargo_takip_no:
                kargo_marker["kargo_takip_no"] = kargo_takip_no
            if kargo_takip_link:
                kargo_marker["kargo_takip_link"] = kargo_takip_link

            # ---- Needs update ----------------------------------------
            if dry_run:
                updated += 1
                consecutive_errors = 0
                out_results.append(
                    {
                        "index": idx,
                        "siparis_id": siparis_id,
                        "siparis_no": siparis_no,
                        "adi": adi,
                        "mevcut_durum": mevcut_durum,
                        "yeni_durum": yeni_durum,
                        "status": "dry_run",
                        **kargo_marker,
                        **({"refetched": True} if refetched else {}),
                    }
                )
            else:
                try:
                    await self._update_one(
                        client,
                        int(siparis_id),
                        yeni_durum,
                        mail_bilgilendir,
                        kargo_takip_no=kargo_takip_no,
                        kargo_takip_link=kargo_takip_link,
                    )
                    updated += 1
                    consecutive_errors = 0
                    out_results.append(
                        {
                            "index": idx,
                            "siparis_id": siparis_id,
                            "siparis_no": siparis_no,
                            "adi": adi,
                            "mevcut_durum": mevcut_durum,
                            "yeni_durum": yeni_durum,
                            "status": "updated",
                            **kargo_marker,
                            **({"refetched": True} if refetched else {}),
                        }
                    )
                except Exception as e:
                    errors += 1
                    consecutive_errors += 1
                    out_results.append(
                        {
                            "index": idx,
                            "siparis_id": siparis_id,
                            "siparis_no": siparis_no,
                            "adi": adi,
                            "mevcut_durum": mevcut_durum,
                            "yeni_durum": yeni_durum,
                            "status": "error",
                            "error": str(e)[:500],
                            **kargo_marker,
                            **({"refetched": True} if refetched else {}),
                        }
                    )
                    if consecutive_errors >= abort_threshold:
                        return self._abort(
                            out_results,
                            updated,
                            errors,
                            skip_no_payment,
                            skip_wrong_odeme_tipi,
                            skip_not_approved,
                            dry_run,
                        )

            # Early exit once we've reached the max_updates limit (only
            # counts actual/dry updates, not skips or errors).
            if max_updates and updated >= max_updates:
                break

            if delay_sec > 0 and idx < len(items) - 1:
                await asyncio.sleep(delay_sec)

        return {
            "updated_count": updated,
            "error_count": errors,
            "skipped_count": (
                skip_no_payment + skip_wrong_odeme_tipi + skip_not_approved + skip_no_kargo_takip_no
            ),
            "skip_no_payment": skip_no_payment,
            "skip_wrong_odeme_tipi": skip_wrong_odeme_tipi,
            "skip_not_approved": skip_not_approved,
            "skip_no_kargo_takip_no": skip_no_kargo_takip_no,
            "refetch_count": refetch_total,
            "dry_run": dry_run,
            "aborted": False,
            "results": out_results,
        }

    # ------------------------------------------------------------------
    async def _refetch_one(self, client: Any, siparis_id: int) -> dict[str, Any] | None:
        """Re-query a single order with ``OdemeGetir=True`` to populate
        ``Odemeler`` (works around Ticimax's inconsistent batch response).
        """

        def _do() -> Any:
            f = client.siparis_factory.WebSiparisFiltre(
                SiparisID=siparis_id,
                UyeID=-1,
                SiparisDurumu=-1,
                OdemeDurumu=-1,
                OdemeTipi=-1,
                EntegrasyonAktarildi=-1,
                TedarikciID=-1,
                OdemeGetir=True,
            )
            s = client.siparis_factory.WebSiparisSayfalama(
                BaslangicIndex=0,
                KayitSayisi=1,
                SiralamaDegeri="Id",
                SiralamaYonu="Desc",
            )
            return client.siparis.SelectSiparis(UyeKodu=client.uye_kodu, f=f, s=s)

        raw = await asyncio.to_thread(_do)
        if raw is None:
            return None
        # Serialize zeep response to a plain dict (same shape as upstream)
        from ticimax_client import serialize_zeep_object  # type: ignore

        ser = serialize_zeep_object(raw)
        if isinstance(ser, list):
            return ser[0] if ser else None
        if isinstance(ser, dict):
            return ser
        return None

    async def _update_one(
        self,
        client: Any,
        siparis_id: int,
        yeni_durum: str,
        mail_bilgilendir: bool,
        *,
        kargo_takip_no: str | None = None,
        kargo_takip_link: str | None = None,
    ) -> None:
        """Single SetSiparisDurum call — runs the blocking SOAP in a thread.

        When ``kargo_takip_no`` (and optionally ``kargo_takip_link``) are
        provided they are written onto the ``SetSiparisDurumRequest`` so
        Ticimax stores the tracking info with the status change.
        """

        def _do() -> Any:
            kwargs: dict[str, Any] = {
                "SiparisID": siparis_id,
                "Durum": yeni_durum,
                "MailBilgilendir": mail_bilgilendir,
            }
            if kargo_takip_no:
                kwargs["KargoTakipNo"] = kargo_takip_no
            if kargo_takip_link:
                kwargs["KargoTakipLink"] = kargo_takip_link
            request = client.siparis_factory.SetSiparisDurumRequest(**kwargs)
            return client.siparis.SetSiparisDurum(UyeKodu=client.uye_kodu, request=request)

        result = await asyncio.to_thread(_do)
        # Ticimax returns a response object: IsError / ErrorMessage
        if result is not None:
            is_error = getattr(result, "IsError", None)
            if is_error is None and isinstance(result, dict):
                is_error = result.get("IsError")
            if is_error:
                err = getattr(result, "ErrorMessage", None)
                if err is None and isinstance(result, dict):
                    err = result.get("ErrorMessage")
                raise RuntimeError(f"Ticimax error: {err!r}")

    def _abort(
        self,
        out_results: list[dict[str, Any]],
        updated: int,
        errors: int,
        skip_no_payment: int,
        skip_wrong_odeme_tipi: int,
        skip_not_approved: int,
        dry_run: bool,
    ) -> dict[str, Any]:
        last_errors = [r.get("error", "?") for r in out_results[-3:] if r.get("status") == "error"]
        raise NodeError(
            "",
            self.type_id,
            f"Aborted: consecutive errors exceeded threshold. "
            f"updated={updated}, errors={errors}, "
            f"skip_no_payment={skip_no_payment}, "
            f"skip_wrong_odeme_tipi={skip_wrong_odeme_tipi}, "
            f"skip_not_approved={skip_not_approved}. Last: {last_errors}",
        )
