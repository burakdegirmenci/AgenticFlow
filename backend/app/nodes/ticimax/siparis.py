"""Ticimax order nodes - manually optimized for MVP."""

from datetime import datetime, timedelta
from typing import Any

from app.engine.context import ExecutionContext
from app.engine.node_base import BaseNode
from app.nodes import register
from app.services.ticimax_service import TicimaxService


@register
class SiparisSelectNode(BaseNode):
    type_id = "ticimax.siparis.select"
    category = "ticimax"
    display_name = "Sipariş Listele"
    description = "Ticimax'tan siparişleri filtreleme ile getirir."
    icon = "shopping-cart"
    color = "#0ea5e9"

    output_schema = {
        "type": "object",
        "properties": {
            "siparisler": {"type": "array"},
            "count": {"type": "integer"},
        },
    }

    config_schema = {
        "type": "object",
        "properties": {
            "baslangic_tarihi": {
                "type": "string",
                "title": "Başlangıç Tarihi (YYYY-MM-DD)",
                "description": (
                    "Sabit başlangıç tarihi. 'son_n_gun' > 0 ise bu alan "
                    "yok sayılır ve tarih dinamik hesaplanır."
                ),
                "default": "",
            },
            "bitis_tarihi": {
                "type": "string",
                "title": "Bitiş Tarihi (YYYY-MM-DD)",
                "default": "",
            },
            "son_n_gun": {
                "type": "integer",
                "title": "Son N Gün (dinamik)",
                "description": (
                    "0 = kapalı (sabit tarihler kullanılır). >0 ise "
                    "baslangic_tarihi = bugün - N gün olarak dinamik "
                    "hesaplanır; schedule trigger'larla kullanışlı."
                ),
                "default": 0,
                "minimum": 0,
                "maximum": 365,
            },
            "siparis_durumu": {
                "type": "integer",
                "title": "Sipariş Durumu",
                "description": "Filtrelenecek sipariş durumu.",
                "default": 2,
                "enum": [-1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
                "enumNames": [
                    "Tümü",
                    "Siparişiniz Alındı",
                    "Onay Bekliyor",
                    "Onaylandı",
                    "Ödeme Bekliyor",
                    "Paketleniyor",
                    "Tedarik Ediliyor",
                    "Kargoya Verildi",
                    "Teslim Edildi",
                    "İptal",
                    "İade",
                ],
            },
            "odeme_durumu": {
                "type": "integer",
                "title": "Ödeme Durumu",
                "default": -1,
                "enum": [-1, 0, 1],
                "enumNames": ["Tümü", "Ödenmedi", "Ödendi"],
            },
            "odeme_tipi": {
                "type": "integer",
                "title": "Ödeme Tipi",
                "description": (
                    "NOT: Ticimax bu filtreyi server tarafında güvenilir "
                    "şekilde uygulamıyor; sonuçları client-side doğrulayın."
                ),
                "default": -1,
                "enum": [-1, 0, 1, 2, 3],
                "enumNames": [
                    "Tümü",
                    "Kredi Kartı",
                    "Havale/EFT",
                    "Kapıda Nakit",
                    "Kapıda Kredi Kartı",
                ],
            },
            "odeme_getir": {
                "type": "boolean",
                "title": "Ödeme Detaylarını Getir",
                "description": (
                    "Odemeler alanını doldurur (OdemeTipi, Onaylandi, Tutar). "
                    "Raporlama workflow'larında açık olmalı."
                ),
                "default": True,
            },
            "kaynaklar": {
                "type": "string",
                "title": "Kaynaklar (virgüllü)",
                "default": "",
            },
            "baslangic_index": {
                "type": "integer",
                "title": "Başlangıç İndeks",
                "default": 0,
            },
            "kayit_sayisi": {
                "type": "integer",
                "title": "Sayfa Büyüklüğü",
                "default": 200,
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
        client = TicimaxService.get_client(context.site)

        filtre_kwargs: dict[str, Any] = {
            "SiparisID": -1,
            "UyeID": -1,
            "SiparisDurumu": int(config.get("siparis_durumu", -1)),
            "OdemeDurumu": int(config.get("odeme_durumu", -1)),
            "OdemeTipi": int(config.get("odeme_tipi", -1)),
            "EntegrasyonAktarildi": -1,
            "TedarikciID": -1,
        }
        if bool(config.get("odeme_getir", False)):
            filtre_kwargs["OdemeGetir"] = True
        bas = (config.get("baslangic_tarihi", "") or "").strip()
        son = (config.get("bitis_tarihi", "") or "").strip()
        son_n_gun = int(config.get("son_n_gun", 0) or 0)
        if son_n_gun > 0:
            # Dynamic rolling window overrides any sabit baslangic_tarihi.
            bas = (datetime.now() - timedelta(days=son_n_gun)).strftime("%Y-%m-%d")
        if bas:
            filtre_kwargs["SiparisTarihiBas"] = bas
        if son:
            filtre_kwargs["SiparisTarihiSon"] = son
        kaynak = (config.get("kaynaklar", "") or "").strip()
        if kaynak:
            filtre_kwargs["SiparisKaynagi"] = kaynak
        filtre = client.siparis_factory.WebSiparisFiltre(**filtre_kwargs)
        sayfalama = client.siparis_factory.WebSiparisSayfalama(
            BaslangicIndex=int(config.get("baslangic_index", 0)),
            KayitSayisi=int(config.get("kayit_sayisi", 50)),
            SiralamaDegeri="Id",
            SiralamaYonu="Desc",
        )

        try:
            siparisler = client.siparis.SelectSiparis(
                UyeKodu=client.uye_kodu, f=filtre, s=sayfalama
            )
        except Exception as e:
            raise RuntimeError(f"SelectSiparis failed: {e}")

        if siparisler is None:
            siparis_list = []
        elif not isinstance(siparisler, list):
            siparis_list = [siparisler]
        else:
            siparis_list = list(siparisler)

        from ticimax_client import serialize_zeep_object  # type: ignore

        serialized = [serialize_zeep_object(s) for s in siparis_list]

        return {
            "siparisler": serialized,
            "count": len(serialized),
        }
