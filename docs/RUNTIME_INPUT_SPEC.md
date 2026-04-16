# Runtime Input Parameters — Specification

> Status: Draft · Date: 2026-04-16

## 1. Problem

When a user clicks "Run" on a workflow, it executes immediately with the
config values baked into the graph at design time. There is no way to:

- Upload a different Excel file for each run
- Enter a date range, customer ID, or any per-run parameter
- Be prompted before execution starts

This makes workflows like "Update stock from today's Excel" impossible
to use in daily operations — the file name is hardcoded.

## 2. Solution

### 2.1 Workflow `input_schema`

A new optional field on the Workflow model: `input_schema` (JSON Schema).
When present, the UI renders a form **before** starting the execution.
The submitted values become `trigger_input` — accessible via
`{{trigger_input.<field>}}` in any node config.

```json
{
  "input_schema": {
    "type": "object",
    "properties": {
      "file": {
        "type": "string",
        "title": "Excel Dosyası",
        "format": "file-upload",
        "description": "Stok güncelleme listesi (.xlsx veya .csv)"
      },
      "dry_run": {
        "type": "boolean",
        "title": "Sadece Önizleme",
        "default": true
      }
    },
    "required": ["file"]
  }
}
```

### 2.2 File Upload Endpoint

```
POST /api/uploads
Content-Type: multipart/form-data
Body: file=<binary>

Response: { "filename": "stok_20260416_143022.xlsx", "size": 12345, "path": "stok_20260416_143022.xlsx" }
```

- Saves to `<cwd>/uploads/` with a timestamp prefix to avoid collisions.
- Returns the filename (not full path) — safe for template use.
- Max size: 10 MB (configurable via env).
- Allowed extensions: .xlsx, .csv.

### 2.3 UI Flow

1. User clicks **"Run"** on a workflow.
2. If workflow has `input_schema`:
   - Modal opens with a form generated from the schema.
   - `format: "file-upload"` fields render a file picker + upload button.
   - Other fields render as text/number/boolean/select based on type.
   - User fills the form, uploads file(s), clicks **"Çalıştır"**.
3. If workflow has NO `input_schema`:
   - Executes immediately (current behaviour, unchanged).
4. On submit:
   - File upload fields: `POST /api/uploads` → get filename → set in `input_data`.
   - Other fields: set directly in `input_data`.
   - `POST /api/workflows/:id/run` with `{ input_data: { file: "stok_20260416.xlsx", dry_run: true } }`.

### 2.4 Template Resolution

Node configs use `{{trigger_input.<field>}}`:

```json
{
  "id": "excel",
  "type": "input.excel_read",
  "data": {
    "config": {
      "file_path": "{{trigger_input.file}}"
    }
  }
}
```

The executor's existing `_resolve_config` already handles this — no
engine changes needed.

## 3. Data Model

### Workflow table change
- New column: `input_schema` (JSON, nullable, default null).
- No migration needed for existing workflows — null = no input form.

### Upload storage
- Directory: `<cwd>/uploads/` (already exists for `input.excel_read`).
- File naming: `<original_stem>_<YYYYMMDD_HHMMSS>.<ext>`.
- Retention: operator responsibility (housekeeping cron in DEPLOYMENT.md).

## 4. Implementation Plan

### Backend (3 files)
1. `POST /api/uploads` endpoint in `app/routers/uploads.py`
2. `input_schema` field on Workflow model + schema
3. Alembic migration for the new column

### Frontend (2 files)
1. `RunWorkflowDialog.tsx` — modal with form-from-schema + file upload
2. Update `WorkflowEditor.tsx` — "Run" button opens dialog when input_schema present

### Tests
- Upload endpoint: happy path + size limit + extension filter
- RunWorkflowDialog: renders fields from schema, submits correct payload
