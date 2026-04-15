"""Seed demo workflows.

Idempotent: skips workflows that already exist (matched by name + site_id).

Usage:
    cd backend
    python -m scripts.seed_db [--site-id N] [--force]

Demos seeded:
    1. "OzelAlan1 Güncelleme (Demo)" — manual → urun.select → parse_stok → log
       (mirrors ProductDetail/worker/parse.py flow, no live mutation)
    2. "Günlük Sipariş Raporu (Demo)" — schedule → siparis.select → excel_export
    3. "Destek Ticketleri AI Sınıflandırma (Demo)" — manual → get_support_tickets
       → ai.prompt → log

The script does NOT activate the demos; the user must enable them from the UI.
"""
from __future__ import annotations

import argparse
import sys
from typing import Any

from app.database import SessionLocal, init_db
from app.models.site import Site
from app.models.workflow import Workflow


def _ozelalan1_demo() -> dict[str, Any]:
    return {
        "name": "OzelAlan1 Güncelleme (Demo)",
        "description": (
            "Aktif ürünleri çeker, stok kodundan baz (model) kodunu türetir "
            "ve log'a yazar. Worker projesinin parse mantığının canvas versiyonu."
        ),
        "graph_json": {
            "nodes": [
                {
                    "id": "trg",
                    "type": "trigger.manual",
                    "position": {"x": 80, "y": 120},
                    "data": {"config": {}},
                },
                {
                    "id": "urn",
                    "type": "ticimax.urun.select",
                    "position": {"x": 320, "y": 120},
                    "data": {
                        "config": {
                            "aktif": 1,
                            "kategori_id": -1,
                            "marka_id": -1,
                            "stok_kodu": "",
                            "baslangic_index": 0,
                            "kayit_sayisi": 25,
                            "siralama_degeri": "id",
                            "siralama_yonu": "Desc",
                        }
                    },
                },
                {
                    "id": "prs",
                    "type": "transform.parse_stok",
                    "position": {"x": 600, "y": 120},
                    "data": {
                        "config": {
                            "source_field": "StokKodu",
                            "target_field": "OzelAlan1",
                            "max_strip": 2,
                            "input_key": "",
                        }
                    },
                },
                {
                    "id": "lg",
                    "type": "output.log",
                    "position": {"x": 880, "y": 120},
                    "data": {
                        "config": {"label": "ozelalan1_demo", "max_length": 4000}
                    },
                },
            ],
            "edges": [
                {"id": "e1", "source": "trg", "target": "urn"},
                {"id": "e2", "source": "urn", "target": "prs"},
                {"id": "e3", "source": "prs", "target": "lg"},
            ],
        },
    }


def _daily_order_report_demo() -> dict[str, Any]:
    return {
        "name": "Günlük Sipariş Raporu (Demo)",
        "description": (
            "Her sabah 06:00'da son siparişleri çeker ve "
            "backend/exports klasörüne .xlsx olarak kaydeder. "
            "Aktif etmek için workflow'u UI'dan açmanız gerekir."
        ),
        "graph_json": {
            "nodes": [
                {
                    "id": "sch",
                    "type": "trigger.schedule",
                    "position": {"x": 80, "y": 120},
                    "data": {"config": {"cron": "0 6 * * *"}},
                },
                {
                    "id": "sip",
                    "type": "ticimax.siparis.select",
                    "position": {"x": 360, "y": 120},
                    "data": {
                        "config": {
                            "baslangic_tarihi": "",
                            "bitis_tarihi": "",
                            "siparis_durumu": -1,
                            "odeme_durumu": -1,
                            "kaynaklar": "",
                            "baslangic_index": 0,
                            "kayit_sayisi": 100,
                        }
                    },
                },
                {
                    "id": "xls",
                    "type": "output.excel_export",
                    "position": {"x": 660, "y": 120},
                    "data": {
                        "config": {
                            "filename": "siparis_raporu",
                            "sheet_name": "Siparisler",
                            "source_field": "",
                            "freeze_header": True,
                        }
                    },
                },
            ],
            "edges": [
                {"id": "e1", "source": "sch", "target": "sip"},
                {"id": "e2", "source": "sip", "target": "xls"},
            ],
        },
    }


def _ticket_classify_demo() -> dict[str, Any]:
    return {
        "name": "Destek Ticket Sınıflandırma (Demo)",
        "description": (
            "Açık destek ticketlarını çeker, AI ile öncelik/konu sınıflandırması "
            "yapar ve sonucu log'a yazar. Canlı yanıt göndermez."
        ),
        "graph_json": {
            "nodes": [
                {
                    "id": "trg",
                    "type": "trigger.manual",
                    "position": {"x": 80, "y": 120},
                    "data": {"config": {}},
                },
                {
                    "id": "tkt",
                    "type": "ticimax.get_support_tickets",
                    "position": {"x": 320, "y": 120},
                    "data": {
                        "config": {
                            "destek_id": -1,
                            "uye_id": -1,
                            "durum_id": -1,
                            "konu_id": -1,
                            "sayfa_no": 1,
                            "kayit_sayisi": 5,
                            "siralama_degeri": "ID",
                            "siralama_yonu": "Desc",
                        }
                    },
                },
                {
                    "id": "ai",
                    "type": "ai.prompt",
                    "position": {"x": 620, "y": 120},
                    "data": {
                        "config": {
                            "provider": "",
                            "model": "",
                            "system": (
                                "Sen bir e-ticaret destek asistanısın. "
                                "Verilen ticketları öncelik (DUSUK/ORTA/YUKSEK) "
                                "ve konu (KARGO/IADE/URUN/HESAP/DIGER) olarak "
                                "sınıflandır. Yanıtını kısa JSON listesi olarak ver."
                            ),
                            "prompt": (
                                "Aşağıdaki destek ticketları için sınıflandırma yap:\n\n"
                                "{{tkt}}"
                            ),
                            "temperature": 0.2,
                            "max_tokens": 2048,
                        }
                    },
                },
                {
                    "id": "lg",
                    "type": "output.log",
                    "position": {"x": 920, "y": 120},
                    "data": {
                        "config": {"label": "ticket_classify", "max_length": 6000}
                    },
                },
            ],
            "edges": [
                {"id": "e1", "source": "trg", "target": "tkt"},
                {"id": "e2", "source": "tkt", "target": "ai"},
                {"id": "e3", "source": "ai", "target": "lg"},
            ],
        },
    }


DEMOS = [
    _ozelalan1_demo,
    _daily_order_report_demo,
    _ticket_classify_demo,
]


def seed(site_id: int, force: bool = False) -> None:
    init_db()
    db = SessionLocal()
    try:
        site = db.query(Site).filter(Site.id == site_id).first()
        if not site:
            print(f"[seed] HATA: site_id={site_id} bulunamadı.", file=sys.stderr)
            print(
                "[seed] Önce UI'dan bir Ticimax sitesi ekleyin "
                "veya --site-id parametresi verin.",
                file=sys.stderr,
            )
            sys.exit(2)

        print(f"[seed] Site: {site.name} ({site.domain})")

        for builder in DEMOS:
            demo = builder()
            existing = (
                db.query(Workflow)
                .filter(Workflow.site_id == site_id, Workflow.name == demo["name"])
                .first()
            )
            if existing and not force:
                print(f"[seed] - SKIP '{demo['name']}' (zaten var, id={existing.id})")
                continue

            if existing and force:
                existing.description = demo["description"]
                existing.graph_json = demo["graph_json"]
                db.commit()
                print(f"[seed] - UPDATE '{demo['name']}' (id={existing.id})")
                continue

            wf = Workflow(
                name=demo["name"],
                description=demo["description"],
                site_id=site_id,
                graph_json=demo["graph_json"],
                is_active=False,
            )
            db.add(wf)
            db.commit()
            db.refresh(wf)
            print(f"[seed] + CREATE '{demo['name']}' (id={wf.id})")

        print("[seed] Tamamlandı.")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed AgenticFlow demo workflows.")
    parser.add_argument(
        "--site-id",
        type=int,
        default=1,
        help="Demo workflow'ların bağlanacağı Ticimax site ID (default: 1)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Mevcut demo workflow'ları güncelle (üzerine yaz)",
    )
    args = parser.parse_args()
    seed(args.site_id, force=args.force)


if __name__ == "__main__":
    main()
