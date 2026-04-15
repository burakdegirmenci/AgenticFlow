"""Shared helpers for AI nodes (template interpolation, provider resolution)."""
from __future__ import annotations

import re
from typing import Any


_TEMPLATE_RE = re.compile(r"\{\{\s*([\w\.]+)\s*\}\}")


def _get_path(obj: Any, path: str) -> Any:
    cur: Any = obj
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit():
            idx = int(part)
            if 0 <= idx < len(cur):
                cur = cur[idx]
            else:
                return None
        else:
            return None
    return cur


def render_template(template: str, context: dict[str, Any]) -> str:
    """Simple `{{path.to.field}}` interpolation against a context dict.

    If a path is not found, the placeholder is left intact (visible to user)
    so they can debug. Values are str()'d.
    """
    if not template:
        return ""

    def sub(m: re.Match[str]) -> str:
        path = m.group(1)
        val = _get_path(context, path)
        if val is None:
            return m.group(0)
        if isinstance(val, (dict, list)):
            import json

            return json.dumps(val, ensure_ascii=False, default=str)
        return str(val)

    return _TEMPLATE_RE.sub(sub, template)


def flatten_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    """Merge parent outputs into a single dict for template access.

    The executor feeds each AI node a dict keyed by parent node_id. For
    templating convenience we also merge all parent values (shallow) so
    users can write `{{StokKodu}}` instead of `{{parent_id.items.0.StokKodu}}`.
    """
    merged: dict[str, Any] = {}
    # Preserve raw parent-keyed structure
    merged.update(inputs)
    # Shallow-merge parent dict outputs
    for v in inputs.values():
        if isinstance(v, dict):
            for k, val in v.items():
                if k not in merged:
                    merged[k] = val
    return merged
