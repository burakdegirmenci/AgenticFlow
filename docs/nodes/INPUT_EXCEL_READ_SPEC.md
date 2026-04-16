# input.excel_read — Node Specification

> Status: Draft · Author: Burak Değirmenci · Date: 2026-04-16

## 1. Problem

Ticimax merchants receive external data as Excel/CSV files daily:
- Warehouse sends a stock update list (SKU + quantity)
- Supplier sends a price list (SKU + new price)
- Marketing team sends product descriptions (SKU + text)
- Accounting sends payment reconciliation (order ID + status)

Today these are entered into Ticimax **manually, row by row**. A single
stock update of 200 rows takes 30–60 minutes and is error-prone.

AgenticFlow can automate the Ticimax side (batch update nodes exist), but
there is no way to **feed external data into a workflow**. This node closes
that gap.

## 2. Solution

A new `input.excel_read` node that:
1. Reads an `.xlsx` or `.csv` file from a configured path.
2. Extracts rows as a list of dicts (one dict per row).
3. Lets the user declare which columns to pick and how to rename them
   — so downstream nodes get the field names they expect.
4. Outputs `{ "items": [...], "count": N }` — the same shape every
   transform/ticimax node already consumes.

## 3. User Stories

### 3.1 Stock Update
> "Depodan her gün `stok_listesi.xlsx` geliyor. A kolonunda StokKodu,
> B kolonunda Miktar var. Bunu Ticimax'taki stok adedine yansıtmak
> istiyorum."

Workflow:
```
trigger.manual
  → input.excel_read(path="uploads/stok_listesi.xlsx",
                     column_map={"StokKodu": "A", "Miktar": "B"})
  → ticimax.save_magaza_stok(batch, dry_run=true)
  → output.log
```

### 3.2 Product Description Update
> "Pazarlama ekibi `aciklamalar.xlsx` gönderiyor. A kolonu UrunKartiID,
> B kolonu yeni açıklama metni."

Workflow:
```
trigger.manual
  → input.excel_read(path="uploads/aciklamalar.xlsx",
                     column_map={"urun_karti_id": "A", "aciklama": "B"},
                     skip_header=true)
  → update_aciklama_batch(dry_run=true)
  → output.log
```

### 3.3 Price Update
> "Tedarikçiden `fiyatlar.csv` geldi. Kolon isimleri Türkçe:
> 'Stok Kodu', 'Yeni Fiyat'."

Workflow:
```
trigger.manual
  → input.excel_read(path="uploads/fiyatlar.csv",
                     column_map={"StokKodu": "Stok Kodu", "Fiyat": "Yeni Fiyat"},
                     header_row=true)
  → ticimax.update_urun_fiyat(batch)
  → output.log
```

## 4. Config Schema

```json
{
  "type": "object",
  "properties": {
    "file_path": {
      "type": "string",
      "title": "Dosya Yolu",
      "description": "uploads/ klasöründeki dosya adı veya tam yol. .xlsx ve .csv desteklenir.",
      "default": ""
    },
    "sheet_name": {
      "type": "string",
      "title": "Sayfa Adı (Excel)",
      "description": "Boş = ilk sayfa. CSV için yok sayılır.",
      "default": ""
    },
    "header_row": {
      "type": "boolean",
      "title": "İlk Satır Başlık mı?",
      "description": "true = ilk satır kolon isimleri olarak kullanılır. false = A,B,C... olarak adlandırılır.",
      "default": true
    },
    "column_map": {
      "type": "object",
      "title": "Kolon Eşlemesi",
      "description": "Çıkış alan adı → kaynak kolon adı. Örn: {\"StokKodu\": \"Stok Kodu\", \"Miktar\": \"Adet\"}. Boş = tüm kolonlar olduğu gibi geçer.",
      "default": {}
    },
    "skip_empty_rows": {
      "type": "boolean",
      "title": "Boş Satırları Atla",
      "default": true
    },
    "max_rows": {
      "type": "integer",
      "title": "Maksimum Satır",
      "description": "0 = sınırsız. Güvenlik sınırı: test için 10, production için 0.",
      "default": 0,
      "minimum": 0
    }
  },
  "required": ["file_path"]
}
```

## 5. Output Schema

```json
{
  "type": "object",
  "properties": {
    "items": {
      "type": "array",
      "description": "Her satır bir dict. Anahtarlar = column_map'teki çıkış alan adları (veya orijinal başlıklar)."
    },
    "count": {
      "type": "integer"
    },
    "source_file": {
      "type": "string",
      "description": "Okunan dosyanın tam yolu."
    },
    "columns": {
      "type": "array",
      "description": "Çıkış kolonlarının sıralı listesi."
    }
  }
}
```

## 6. Behaviour Rules

1. **File resolution**: `file_path` is resolved relative to `<backend_cwd>/uploads/`.
   Absolute paths are allowed but logged as a warning.
2. **Format detection**: `.csv` → `csv.DictReader`; `.xlsx` → `openpyxl`.
   `.xls` (legacy) is NOT supported (no xlrd dependency).
3. **column_map empty** → all columns pass through with their original names
   (from header row, or A/B/C if `header_row=false`).
4. **column_map non-empty** → ONLY the mapped columns are included in output.
   Source columns not mentioned are dropped. Missing source columns → `None`.
5. **Type coercion**: all cell values are converted to Python primitives
   (str, int, float, bool, None). Dates → ISO-8601 strings. Formulas →
   their cached value (openpyxl `data_only=True`).
6. **Empty row**: a row where ALL mapped columns are None/empty-string.
   Skipped when `skip_empty_rows=true`.
7. **max_rows**: applied AFTER skipping empties, BEFORE output. 0 = no limit.
8. **Error on missing file**: `NodeError` with a clear message + the
   resolved path.
9. **Error on unreadable format**: `NodeError` if extension is not
   `.xlsx` or `.csv`.

## 7. File Upload Path

For v1.x (self-hosted, single-tenant):
- User places files in `<backend>/uploads/` (or the Docker mount).
- docker-compose.yml already mounts `./backend/exports/`; we add
  `./uploads/:/app/uploads/` as a new volume.
- Future: UI file-upload widget that POSTs to `/api/uploads` and writes
  to this directory. Out of scope for this node's first version.

## 8. Security

- File path must resolve INSIDE `uploads/` or `exports/`. Path traversal
  (`../../../etc/passwd`) is blocked via `pathlib.resolve()` + prefix check.
- Max file size is not enforced at the node level (openpyxl streams, but
  a 500 MB Excel would OOM). Recommendation: operator sets a reasonable
  limit at the reverse-proxy layer or via an upload endpoint.
- File contents are treated as untrusted data. No `eval`, no macro
  execution, no formula interpretation.

## 9. Dependencies

- `openpyxl` — already a runtime dep (used by `output.excel_export`).
- `csv` — stdlib.
- No new dependencies needed.

## 10. Test Plan

| Test | Type | What |
|---|---|---|
| Read .xlsx with header row | unit | 3-row fixture → 3 items |
| Read .csv with header row | unit | same |
| Read without header (A,B,C naming) | unit | |
| column_map renames + drops | unit | |
| column_map with missing source column → None | unit | |
| skip_empty_rows filters blanks | unit | |
| max_rows truncates | unit | |
| File not found → NodeError | unit | |
| Path traversal blocked | unit | |
| .xls rejected | unit | |
| Contract test passes (node in registry) | contract | |
