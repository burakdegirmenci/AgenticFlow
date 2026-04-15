"""Seed: create 'Destek Yanıtlama' workflow with 16 nodes.

Usage:
    cd backend
    python -m app.seeds.support_workflow
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure backend is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.database import SessionLocal, init_db
from app.models.workflow import Workflow

WORKFLOW_NAME = "Destek Yanıtlama"

SYSTEM_PROMPT = """\
Sen Demo Store müşteri destek asistanısın. Sana bir destek talebi (ticket) \
ve ilgili veriler (mesaj geçmişi, müşteri profili, siparişler, iade/değişim \
talepleri, adresler, aktif kampanyalar, ödeme bildirimleri) verilecek. \
Görevin bu bilgileri analiz edip müşteriye profesyonel bir yanıt taslağı \
oluşturmak.

## Yanıt Kuralları
- Her zaman "Merhaba," ile başla, "Saygılarımızla." ile bitir
- Resmi ama sıcak ton, kısa ve net
- Veri varsa somut bilgi ver (kargo takip no, sipariş durumu, tutar vb.)
- Varsayımda bulunma, emin olmadığın bilgiyi verme
- Müşterinin adını kullan (biliniyorsa)

## İş Politikaları
- Online alışverişlerde değişim yapılmaz → iade + yeniden sipariş
- Sipariş sonrası adres değişikliği yapılamaz
- Kargoya verilen sipariş iptal edilemez
- İade süreci: Kolay iade kodu oluştur → DHL kargo ile geri gönder → merkez kontrol → para iadesi
- Kredi kartına iade: Bankaya bağlı olarak 1-4 hafta içinde hesaba yansır
- Havale ile ödeme iadesi: IBAN bilgisi gerekir

## Sipariş Durumu Kodları
- Siparişiniz Alındı → Yeni sipariş, henüz işlenmedi
- Onaylandı → Ödeme onaylandı, hazırlanıyor
- Kargoya Verildi → Kargo firmasına teslim edildi
- Teslim Edildi → Müşteriye ulaştı
- İade → İade süreci başlatılmış
- İptal → Sipariş iptal edilmiş

## Talimat
Aşağıdaki verileri analiz et ve müşteriye uygun bir yanıt oluştur. \
Yanıtın yalnızca müşteriye gönderilecek metin olsun — dahili notlar ekleme. \
Veriler Ticimax SOAP API'den geldiği için iç içe JSON yapısında olabilir; \
ilgili alanları (Konu, Mesaj, Cevap, SiparisDurumu, KargoTakipNo vb.) bul \
ve kullan.\
"""

PROMPT_TEMPLATE = """\
## Destek Talebi Bilgisi
{{n2.result}}

## Mesaj Geçmişi
{{n3.result}}

## Müşterinin Son Siparişleri
{{n4.result}}

## Müşteri Bilgisi
{{n6.result}}

## Müşteri Adresleri
{{n7.result}}

## İade Talepleri
{{n8.result}}

## Değişim Talepleri
{{n9.result}}

## Aktif Kampanyalar
{{n10.result}}

## Ödeme Bildirimleri (Havale/EFT)
{{n11.result}}

## Son Siparişin İade Ödeme Durumu
{{n12.result}}

## Son Siparişin Kargo Takip Bilgisi
{{n13.result}}

## Son Siparişin Ödeme Detayı
{{n14.result}}

## Son Siparişe Uygulanan Kampanyalar
{{n15.result}}

## Son Siparişin Durum Geçmişi
{{n16.result}}

---
Yukarıdaki bilgileri analiz et ve müşteriye uygun bir yanıt taslağı oluştur.\
"""

GRAPH_JSON = {
    "nodes": [
        {
            "id": "n1",
            "type": "trigger.manual",
            "position": {"x": 100, "y": 300},
            "data": {
                "label": "Ticket Trigger",
                "config": {},
            },
        },
        {
            "id": "n2",
            "type": "ticimax.get_support_tickets",
            "position": {"x": 400, "y": 40},
            "data": {
                "label": "Ticket Bilgisi",
                "config": {
                    "destek_id": "{{n1.input.ticket_id}}",
                    "uye_id": -1,
                    "durum_id": -1,
                    "konu_id": -1,
                    "kayit_sayisi": 1,
                },
            },
        },
        {
            "id": "n3",
            "type": "ticimax.get_ticket_messages",
            "position": {"x": 400, "y": 130},
            "data": {
                "label": "Mesaj Geçmişi",
                "config": {
                    "destek_id": "{{n1.input.ticket_id}}",
                    "uye_id": "{{n1.input.uye_id}}",
                },
            },
        },
        {
            "id": "n4",
            "type": "ticimax.select_siparis",
            "position": {"x": 400, "y": 220},
            "data": {
                "label": "Müşteri Siparişleri",
                "config": {
                    "uye_id": "{{n1.input.uye_id}}",
                    "kayit_sayisi": 20,
                    "siralama_degeri": "Id",
                    "siralama_yonu": "Desc",
                    "exclude_durum": "Siparişiniz Alındı",
                },
            },
        },
        # ---- Yeni node'lar ----
        {
            "id": "n6",
            "type": "ticimax.select_uyeler",
            "position": {"x": 400, "y": 310},
            "data": {
                "label": "Müşteri Bilgisi",
                "config": {
                    "uye_id": "{{n1.input.uye_id}}",
                    "kayit_sayisi": 1,
                },
            },
        },
        {
            "id": "n7",
            "type": "ticimax.select_uye_adres",
            "position": {"x": 400, "y": 400},
            "data": {
                "label": "Müşteri Adresleri",
                "config": {
                    "uye_id": "{{n1.input.uye_id}}",
                },
            },
        },
        {
            "id": "n8",
            "type": "ticimax.select_iade_talebi",
            "position": {"x": 400, "y": 490},
            "data": {
                "label": "İade Talepleri",
                "config": {
                    "siparis_id": -1,
                    "kayit_sayisi": 5,
                },
            },
        },
        {
            "id": "n9",
            "type": "ticimax.select_degisim_talebi",
            "position": {"x": 400, "y": 580},
            "data": {
                "label": "Değişim Talepleri",
                "config": {
                    "siparis_id": -1,
                    "kayit_sayisi": 5,
                },
            },
        },
        # ---- Yeni veri node'ları (2. dalga) ----
        {
            "id": "n10",
            "type": "ticimax.get_kampanya_v2",
            "position": {"x": 400, "y": 670},
            "data": {
                "label": "Aktif Kampanyalar",
                "config": {
                    "kampanya_id": -1,
                    "aktif": 1,
                    "sayfa_no": 1,
                    "kayit_sayisi": 20,
                },
            },
        },
        {
            "id": "n11",
            "type": "ticimax.select_odeme_bildirimi",
            "position": {"x": 400, "y": 760},
            "data": {
                "label": "Ödeme Bildirimleri",
                "config": {
                    "siparis_id": -1,
                    "uye_id": "{{n1.input.uye_id}}",
                },
            },
        },
        # ---- Zincirleme node: n4 → n12 (sipariş ID'den iade ödeme) ----
        {
            "id": "n12",
            "type": "ticimax.select_iade_odeme",
            "position": {"x": 600, "y": 220},
            "data": {
                "label": "İade Ödeme Durumu",
                "config": {
                    "siparis_id": "{{n4.result.0.ID}}",
                    "iade_id": -1,
                },
            },
        },
        # ---- Zincirleme node'lar: n4 → n13,n14,n15,n16 ----
        {
            "id": "n13",
            "type": "ticimax.siparis_kargo_takip_no_kontrol",
            "position": {"x": 600, "y": 310},
            "data": {
                "label": "Kargo Takip Kontrolü",
                "config": {
                    "siparis_id": "{{n4.result.0.ID}}",
                },
            },
        },
        {
            "id": "n14",
            "type": "ticimax.select_siparis_odeme",
            "position": {"x": 600, "y": 400},
            "data": {
                "label": "Sipariş Ödeme Detayı",
                "config": {
                    "siparis_id": "{{n4.result.0.ID}}",
                    "odeme_id": -1,
                },
            },
        },
        {
            "id": "n15",
            "type": "ticimax.select_siparis_kampanya",
            "position": {"x": 600, "y": 490},
            "data": {
                "label": "Sipariş Kampanyaları",
                "config": {
                    "siparis_id": "{{n4.result.0.ID}}",
                },
            },
        },
        {
            "id": "n16",
            "type": "ticimax.select_siparis_durum_log",
            "position": {"x": 600, "y": 580},
            "data": {
                "label": "Sipariş Durum Geçmişi",
                "config": {
                    "siparis_id": "{{n4.result.0.ID}}",
                },
            },
        },
        # ---- AI node ----
        {
            "id": "n5",
            "type": "ai.prompt",
            "position": {"x": 800, "y": 300},
            "data": {
                "label": "AI Yanıt Oluştur",
                "config": {
                    "provider": "google_genai",
                    "model": "gemini-2.5-flash",
                    "system": SYSTEM_PROMPT,
                    "prompt": PROMPT_TEMPLATE,
                    "temperature": 0.3,
                    "max_tokens": 4096,
                },
            },
        },
    ],
    "edges": [
        # Trigger → veri node'ları
        {"id": "e1", "source": "n1", "target": "n2"},
        {"id": "e2", "source": "n1", "target": "n3"},
        {"id": "e3", "source": "n1", "target": "n4"},
        {"id": "e7", "source": "n1", "target": "n6"},
        {"id": "e8", "source": "n1", "target": "n7"},
        {"id": "e9", "source": "n1", "target": "n8"},
        {"id": "e10", "source": "n1", "target": "n9"},
        {"id": "e15", "source": "n1", "target": "n10"},
        {"id": "e16", "source": "n1", "target": "n11"},
        # Veri node'ları → AI
        {"id": "e4", "source": "n2", "target": "n5"},
        {"id": "e5", "source": "n3", "target": "n5"},
        {"id": "e6", "source": "n4", "target": "n5"},
        {"id": "e11", "source": "n6", "target": "n5"},
        {"id": "e12", "source": "n7", "target": "n5"},
        {"id": "e13", "source": "n8", "target": "n5"},
        {"id": "e14", "source": "n9", "target": "n5"},
        {"id": "e17", "source": "n10", "target": "n5"},
        {"id": "e18", "source": "n11", "target": "n5"},
        # Zincirleme: n4 siparişleri → sipariş detay node'ları
        {"id": "e19", "source": "n4", "target": "n12"},
        {"id": "e20", "source": "n12", "target": "n5"},
        {"id": "e21", "source": "n4", "target": "n13"},
        {"id": "e22", "source": "n13", "target": "n5"},
        {"id": "e23", "source": "n4", "target": "n14"},
        {"id": "e24", "source": "n14", "target": "n5"},
        {"id": "e25", "source": "n4", "target": "n15"},
        {"id": "e26", "source": "n15", "target": "n5"},
        {"id": "e27", "source": "n4", "target": "n16"},
        {"id": "e28", "source": "n16", "target": "n5"},
    ],
}


def seed() -> int:
    """Create or update the 'Destek Yanıtlama' workflow. Returns workflow ID."""
    init_db()
    db = SessionLocal()
    try:
        existing = db.query(Workflow).filter(Workflow.name == WORKFLOW_NAME).first()
        if existing:
            existing.graph_json = GRAPH_JSON
            existing.description = "Destek talebini analiz edip AI ile yanıt taslağı oluşturur."
            db.commit()
            db.refresh(existing)
            print(f"Updated existing workflow: id={existing.id}")
            return existing.id

        wf = Workflow(
            name=WORKFLOW_NAME,
            description="Destek talebini analiz edip AI ile yanıt taslağı oluşturur.",
            site_id=2,
            graph_json=GRAPH_JSON,
            is_active=False,
        )
        db.add(wf)
        db.commit()
        db.refresh(wf)
        print(f"Created workflow: id={wf.id}, name='{wf.name}'")
        return wf.id
    finally:
        db.close()


if __name__ == "__main__":
    wf_id = seed()
    print(f"Done. Workflow ID: {wf_id}")
