# Excel Preview + Column Mapping — Specification

> Status: Draft · Date: 2026-04-16

## Problem

When a user uploads an Excel file at runtime, the system doesn't know
which columns contain what data. Column names vary between files:
one day "Stok Kodu", next day "SKU", next "Ürün Kodu". Hardcoding
`column_map` at workflow design time is fragile.

## Solution: Upload → Preview → Map → Run

```
User clicks "Run"
  → File upload dialog
  → User picks Excel
  → POST /api/uploads → saves, returns filename
  → GET /api/uploads/<filename>/preview → returns columns + 3 sample rows
  → Dialog shows preview table + per-column mapping dropdown
  → User maps: "Stok Kodu" → StokKodu, "Adet" → Miktar
  → Clicks "Çalıştır"
  → POST /api/workflows/:id/run
      input_data: { file: "xxx.xlsx", column_map: {"StokKodu":"Stok Kodu","Miktar":"Adet"} }
  → Excel node resolves: file_path={{trigger_input.file}}, column_map={{trigger_input.column_map}}
```

## API

### GET /api/uploads/:filename/preview

```json
{
  "filename": "stok_20260416.xlsx",
  "columns": ["Stok Kodu", "Adet", "Depo Notu"],
  "sample_rows": [
    {"Stok Kodu": "SKU-001", "Adet": 10, "Depo Notu": "Raf A3"},
    {"Stok Kodu": "SKU-002", "Adet": 20, "Depo Notu": "Raf B1"},
    {"Stok Kodu": "SKU-003", "Adet": 0, "Depo Notu": "Stoksuz"}
  ],
  "total_rows": 200
}
```

## Target Fields (dropdown options)

Common Ticimax fields the user can map to:

| Field | Description |
|---|---|
| StokKodu | Ürün stok kodu |
| UrunKartiID | Ürün ID |
| Miktar | Stok adedi |
| Fiyat | Satış fiyatı |
| UrunAdi | Ürün adı |
| Aciklama | Ürün açıklaması |
| OzelAlan1 | Özel alan 1 |
| OzelAlan2-5 | Özel alanlar |
| Barkod | Barkod |
| (kullanma) | Bu kolonu atla |

The list is provided by the frontend as a constant. Future: pull
dynamically from the target node's config_schema.
