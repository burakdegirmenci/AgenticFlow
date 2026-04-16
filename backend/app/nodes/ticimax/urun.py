"""Ticimax product nodes - manually optimized for MVP."""

from typing import Any

from app.engine.context import ExecutionContext
from app.engine.node_base import BaseNode
from app.nodes import register
from app.services.ticimax_service import TicimaxService


@register
class UrunSelectNode(BaseNode):
    type_id = "ticimax.urun.select"
    category = "ticimax"
    display_name = "Ürün Listele"
    description = "Ticimax'tan ürünleri filtreleme ve sayfalama ile getirir."
    icon = "package"
    color = "#0ea5e9"

    output_schema = {
        "type": "object",
        "properties": {
            "urunler": {"type": "array"},
            "count": {"type": "integer"},
        },
    }

    config_schema = {
        "type": "object",
        "properties": {
            "aktif": {
                "type": "integer",
                "title": "Aktif Durumu",
                "default": 1,
                "enum": [-1, 0, 1],
                "enumNames": ["Hepsi", "Pasif", "Aktif"],
            },
            "kategori_id": {
                "type": "integer",
                "title": "Kategori ID",
                "default": -1,
            },
            "marka_id": {
                "type": "integer",
                "title": "Marka ID",
                "default": -1,
            },
            "stok_kodu": {
                "type": "string",
                "title": "Stok Kodu (filtre)",
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
                "default": 100,
                "minimum": 1,
                "maximum": 1000,
            },
            "siralama_degeri": {
                "type": "string",
                "title": "Sıralama Alanı",
                "default": "id",
            },
            "siralama_yonu": {
                "type": "string",
                "title": "Sıralama Yönü",
                "default": "Desc",
                "enum": ["Asc", "Desc"],
            },
            "resim_durumu": {
                "type": "string",
                "title": "Resim Durumu",
                "description": "Tumu = resimli + resimsiz hepsi. Resimler alanı dolu gelir.",
                "default": "Tumu",
                "enum": ["Tumu", ""],
            },
            "pasif_resimleri_getir": {
                "type": "boolean",
                "title": "Pasif Resimleri de Getir",
                "default": False,
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

        filtre_kwargs: dict[str, Any] = dict(
            UrunKartiID=-1,
            MarkaID=int(config.get("marka_id", -1)),
            KategoriID=int(config.get("kategori_id", -1)),
            TedarikciID=-1,
            Aktif=int(config.get("aktif", 1)),
            StokKodu=config.get("stok_kodu", "") or "",
        )
        resim_durumu = (config.get("resim_durumu") or "").strip()
        if resim_durumu:
            filtre_kwargs["ResimDurumu"] = resim_durumu
        if config.get("pasif_resimleri_getir"):
            filtre_kwargs["PasifResimleriGetir"] = True
        filtre = client.urun_factory.UrunFiltre(**filtre_kwargs)
        sayfalama = client.urun_factory.UrunSayfalama(
            BaslangicIndex=int(config.get("baslangic_index", 0)),
            KayitSayisi=int(config.get("kayit_sayisi", 100)),
            SiralamaDegeri=config.get("siralama_degeri", "id"),
            SiralamaYonu=config.get("siralama_yonu", "Desc"),
        )

        urunler = client.urun.SelectUrun(UyeKodu=client.uye_kodu, f=filtre, s=sayfalama)

        if urunler is None:
            urunler_list = []
        elif not isinstance(urunler, list):
            urunler_list = [urunler]
        else:
            urunler_list = list(urunler)

        # Serialize zeep objects to plain dicts
        from ticimax_client import serialize_zeep_object  # type: ignore

        serialized = [serialize_zeep_object(u) for u in urunler_list]

        return {
            "urunler": serialized,
            "count": len(serialized),
        }
