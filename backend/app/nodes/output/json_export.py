"""JSON export node - writes inputs (or a subtree) as pretty JSON to disk.

Output lands in `<backend cwd>/exports/<filename>_<YYYYMMDD_HHMMSS>.json`.

Config:
    filename: base name without extension (default: "export")
    source_field: dotted path into the input to serialize; if empty, the
        entire inputs dict is serialized.
    indent: JSON indent level (default 2). Set to 0 for compact output.
"""

import json
import os
from datetime import datetime
from typing import Any

from app.engine.context import ExecutionContext
from app.engine.node_base import BaseNode
from app.nodes import register


def _walk_dotted(obj: Any, path: str) -> Any:
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


@register
class JsonExportNode(BaseNode):
    type_id = "output.json_export"
    category = "output"
    display_name = "JSON Export"
    description = (
        "Gelen veriyi .json dosyasına yazar. Kaynak alan belirtilmezse "
        "tüm parent çıktıları dahil edilir."
    )
    icon = "braces"
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
                    "Boşsa tüm inputs serileştirilir. Örn: 'result.UrunList' veya 'urunler.0'."
                ),
                "default": "",
            },
            "indent": {
                "type": "integer",
                "title": "Girinti",
                "default": 2,
                "minimum": 0,
                "maximum": 8,
            },
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string"},
            "bytes_written": {"type": "integer"},
        },
    }

    async def execute(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        source_field = (config.get("source_field") or "").strip()

        payload: Any
        if source_field:
            payload = None
            for parent_output in inputs.values():
                if not isinstance(parent_output, (dict, list)):
                    continue
                candidate = _walk_dotted(parent_output, source_field)
                if candidate is not None:
                    payload = candidate
                    break
            if payload is None:
                return {
                    "file_path": "",
                    "bytes_written": 0,
                    "note": f"source_field '{source_field}' did not resolve",
                }
        else:
            payload = inputs

        exports_dir = os.path.join(os.getcwd(), "exports")
        os.makedirs(exports_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = (config.get("filename") or "export") or "export"
        file_path = os.path.join(exports_dir, f"{filename}_{ts}.json")

        indent = int(config.get("indent", 2))
        indent_arg: int | None = indent if indent > 0 else None

        text = json.dumps(payload, default=str, ensure_ascii=False, indent=indent_arg)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(text)

        return {
            "file_path": file_path,
            "bytes_written": len(text.encode("utf-8")),
        }
