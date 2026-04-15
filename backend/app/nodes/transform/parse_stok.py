"""Parse stok kodu → OzelAlan1 transform node.

Ported from ProductDetail/worker/parse.py. Strips up to 2 trailing variant
segments from a stok_kodu to derive a base (model) code.

Rules (segment is variant if):
- digits only (01, 18, 378)
- alpha only and len >= 2 (YS, GR, KMJ)
- mixed alphanumeric (EA4, hz4)
Single-char segments (R, 7) are preserved.
"""

from typing import Any

from app.engine.context import ExecutionContext
from app.engine.node_base import BaseNode
from app.nodes import register


def _is_variant_segment(seg: str) -> bool:
    if not seg:
        return False
    if len(seg) == 1:
        return False
    if seg.isdigit():
        return True
    if seg.isalpha():
        return True
    if seg.isalnum() and any(c.isalpha() for c in seg) and any(c.isdigit() for c in seg):
        return True
    return False


def derive_base_stok(stok_kodu: str, max_strip: int = 2) -> str:
    if not stok_kodu:
        return ""
    parts = stok_kodu.split("-")
    if len(parts) <= 1:
        return stok_kodu
    for _ in range(max_strip):
        if len(parts) > 1 and _is_variant_segment(parts[-1]):
            parts.pop()
        else:
            break
    return "-".join(parts)


@register
class ParseStokNode(BaseNode):
    type_id = "transform.parse_stok"
    category = "transform"
    display_name = "Stok Kodu Ayrıştır"
    description = "Stok kodundan baz (OzelAlan1) kodu türetir. Varyant segmentlerini atar."
    icon = "scissors"
    color = "#8b5cf6"

    input_schema = {
        "type": "object",
        "properties": {
            "items": {"type": "array", "description": "Üzerinde çalışılacak kayıtlar"},
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "items": {"type": "array"},
            "count": {"type": "integer"},
        },
    }

    config_schema = {
        "type": "object",
        "properties": {
            "source_field": {
                "type": "string",
                "title": "Kaynak Alan",
                "description": "Parse edilecek stok kodu alanı",
                "default": "StokKodu",
            },
            "target_field": {
                "type": "string",
                "title": "Hedef Alan",
                "description": "Baz kodun yazılacağı alan",
                "default": "OzelAlan1",
            },
            "max_strip": {
                "type": "integer",
                "title": "Maks. Atılacak Segment",
                "default": 2,
                "minimum": 0,
                "maximum": 5,
            },
            "input_key": {
                "type": "string",
                "title": "Giriş Anahtarı",
                "description": "Önceki node çıktısındaki dizi anahtarı (boş = tüm output bir dizi)",
                "default": "",
            },
        },
    }

    async def execute(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        source_field = config.get("source_field", "StokKodu")
        target_field = config.get("target_field", "OzelAlan1")
        max_strip = int(config.get("max_strip", 2))
        input_key = config.get("input_key", "") or ""

        # Resolve input items: prefer explicit key, else first array-valued key
        items = _resolve_items(inputs, input_key)

        result: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                result.append(item)
                continue
            stok = item.get(source_field) or ""
            base = derive_base_stok(str(stok), max_strip=max_strip)
            new_item = dict(item)
            new_item[target_field] = base
            result.append(new_item)

        return {"items": result, "count": len(result)}


def _resolve_items(inputs: dict[str, Any], input_key: str) -> list[Any]:
    if input_key and input_key in inputs:
        val = inputs[input_key]
        return list(val) if isinstance(val, list) else [val]
    # Walk merged upstream outputs for the first list-valued key.
    # Skip underscore-prefixed keys (e.g. `_branches` from logic.if) which
    # are internal routing markers, not payload data.
    for v in inputs.values():
        if isinstance(v, dict):
            for k, inner in v.items():
                if isinstance(k, str) and k.startswith("_"):
                    continue
                if isinstance(inner, list):
                    return inner
        if isinstance(v, list):
            return v
    return []
