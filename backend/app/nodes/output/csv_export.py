"""CSV export node - writes array data to a CSV file.

Where do the files go?
    <backend cwd>/exports/<filename>_<YYYYMMDD_HHMMSS>.csv

The backend's current working directory is the folder it was launched from
(typically `AgenticFlow/backend/`), so files land in
`AgenticFlow/backend/exports/`.

Finding the list of rows:
    1. If `source_field` is set, we treat it as a dotted path and walk it
       (e.g. `result.UrunList` or `siparisler`). If the value at that path
       is a list, we use it.
    2. Otherwise we recursively search the parent outputs for the first
       list-of-dicts we can find. This handles the typical Ticimax SOAP
       shape `{"result": {"UrunList": [...], "Sayfalama": {...}}}` without
       any configuration.
"""

import csv
import os
from datetime import datetime
from typing import Any

from app.engine.context import ExecutionContext
from app.engine.node_base import BaseNode
from app.nodes import register


def _walk_dotted(obj: Any, path: str) -> Any:
    """Walk a dotted path through nested dicts/lists. Returns None if missing."""
    cur = obj
    for part in path.split("."):
        if part == "":
            continue
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list):
            try:
                idx = int(part)
                cur = cur[idx]
            except (ValueError, IndexError):
                return None
        else:
            return None
        if cur is None:
            return None
    return cur


def _find_first_list_of_dicts(obj: Any, max_depth: int = 6) -> list[Any] | None:
    """Recursively search for the first non-empty list whose first item is a dict.

    Depth-first, preferring shallower matches. Returns None if nothing found.

    Note: only the first element is type-checked for perf reasons, so the
    returned list may contain non-dict elements — callers should handle that
    defensively (skip non-dicts in row iteration).
    """
    if max_depth < 0:
        return None
    if isinstance(obj, list):
        if obj and isinstance(obj[0], dict):
            return obj
        # A list of non-dicts is not useful for CSV rows.
        return None
    if isinstance(obj, dict):
        # First pass: shallow scan for a direct list-of-dicts child.
        for v in obj.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v
        # Second pass: recurse into children.
        for v in obj.values():
            found = _find_first_list_of_dicts(v, max_depth - 1)
            if found is not None:
                return found
    return None


@register
class CsvExportNode(BaseNode):
    type_id = "output.csv_export"
    category = "output"
    display_name = "CSV Export"
    description = (
        "Parent node çıktısındaki listeyi CSV dosyasına yazar. "
        "Dosya `backend/exports/<ad>_<zaman>.csv` yoluna kaydedilir."
    )
    icon = "download"
    color = "#16a34a"

    config_schema = {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "title": "Dosya Adı (uzantısız)",
                "default": "export",
            },
            "source_field": {
                "type": "string",
                "title": "Kaynak Alan (dotted path)",
                "description": (
                    "Örn: 'result.UrunList' veya 'urunler'. "
                    "Boşsa otomatik olarak ilk dict-listesi bulunur."
                ),
                "default": "",
            },
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string"},
            "rows_written": {"type": "integer"},
        },
    }

    async def execute(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        source_field = (config.get("source_field") or "").strip()
        # Heterogeneous list: the helper only validates the first element is
        # a dict, and callers may supply dotted paths to lists with mixed
        # types. The loop below skips non-dict rows defensively.
        rows: list[Any] = []
        source_parent: str = ""

        for parent_id, parent_output in inputs.items():
            if not isinstance(parent_output, (dict, list)):
                continue
            if source_field:
                candidate = _walk_dotted(parent_output, source_field)
                if isinstance(candidate, list) and candidate:
                    rows = candidate
                    source_parent = parent_id
                    break
            else:
                found = _find_first_list_of_dicts(parent_output)
                if found:
                    rows = found
                    source_parent = parent_id
                    break

        if not rows:
            return {
                "file_path": "",
                "rows_written": 0,
                "note": (
                    f"no list-of-dicts found in inputs from {list(inputs.keys())}"
                    if not source_field
                    else f"source_field '{source_field}' did not resolve to a list"
                ),
            }

        # Build output path
        exports_dir = os.path.join(os.getcwd(), "exports")
        os.makedirs(exports_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = (config.get("filename") or "export") or "export"
        file_path = os.path.join(exports_dir, f"{filename}_{ts}.csv")

        # Collect all keys (union).
        keys: list[str] = []
        seen: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            for k in row.keys():
                if k not in seen:
                    seen.add(k)
                    keys.append(k)

        with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                if isinstance(row, dict):
                    flat = {
                        k: (v if isinstance(v, (str, int, float, bool)) or v is None else str(v))
                        for k, v in row.items()
                    }
                    writer.writerow(flat)

        return {
            "file_path": file_path,
            "rows_written": len(rows),
            "source_parent": source_parent,
        }
