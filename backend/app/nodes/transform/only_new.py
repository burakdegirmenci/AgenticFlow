"""Only-new transform - emit items whose id_field is not in the previous snapshot.

Uses the ``polling_snapshots`` table to remember which IDs have been seen in
prior runs of this specific (workflow_id, node_id). Intended for polling
flows: ``polling(60s) → ticimax.select_siparis → only_new(id_field="SiparisId")
→ process``.

First-run behavior: on the very first execution (no snapshot exists) the node
seeds the snapshot with the current IDs and returns ``new_items=[]``. This
avoids a thundering-herd effect where the first activation would process every
historical row. Set ``emit_on_first_run=true`` to opt out.
"""

from datetime import datetime
from typing import Any

from app.engine.context import ExecutionContext
from app.engine.node_base import BaseNode
from app.nodes import register

_MAX_REMEMBERED_IDS = 10_000


def _find_first_list_of_dicts(obj: Any, max_depth: int = 6) -> list[dict] | None:
    """Walk an arbitrary structure (dicts/lists) and return the first list of dicts."""
    if max_depth < 0:
        return None
    if isinstance(obj, list):
        if obj and all(isinstance(x, dict) for x in obj):
            return obj
        for item in obj:
            found = _find_first_list_of_dicts(item, max_depth - 1)
            if found is not None:
                return found
        return None
    if isinstance(obj, dict):
        for val in obj.values():
            found = _find_first_list_of_dicts(val, max_depth - 1)
            if found is not None:
                return found
    return None


def _resolve_items(inputs: dict[str, Any], input_key: str) -> list[dict]:
    """Find the list of dicts inside ``inputs``.

    Priority:
      1. If ``input_key`` is provided and points to a list, use it.
      2. Otherwise walk the merged parent outputs recursively and pick the
         first list of dicts encountered (same policy as csv_export).
    """
    if input_key and input_key in inputs:
        val = inputs[input_key]
        if isinstance(val, list):
            return [v for v in val if isinstance(v, dict)]
        if isinstance(val, dict):
            found = _find_first_list_of_dicts(val)
            if found is not None:
                return found
    found = _find_first_list_of_dicts(inputs)
    return found or []


@register
class OnlyNewNode(BaseNode):
    type_id = "transform.only_new"
    category = "transform"
    display_name = "Sadece Yeni Kayıtlar"
    description = (
        "Önceki çalıştırmalarda görülmeyen kayıtları döner. "
        "Polling workflow'larında yeni sipariş/ürün/ticket izlemek için."
    )
    icon = "git-branch"
    color = "#8b5cf6"

    input_schema = {
        "type": "object",
        "properties": {"items": {"type": "array"}},
    }

    output_schema = {
        "type": "object",
        "properties": {
            "new_items": {"type": "array"},
            "count": {"type": "integer"},
            "total_seen": {"type": "integer"},
            "first_run": {"type": "boolean"},
        },
    }

    config_schema = {
        "type": "object",
        "properties": {
            "id_field": {
                "type": "string",
                "title": "ID Alanı",
                "description": "Benzersiz tanımlayıcı alan adı (örn: ID, SiparisId, UyeID)",
                "default": "ID",
            },
            "input_key": {
                "type": "string",
                "title": "Giriş Anahtarı",
                "description": "Parent node çıktısında liste hangi anahtarda? Boş bırak = otomatik bul.",
                "default": "",
            },
            "emit_on_first_run": {
                "type": "boolean",
                "title": "İlk Çalıştırmada Da Yay",
                "description": "True = ilk çalıştırmada tüm kayıtları yay. False = sadece snapshot'a kaydet.",
                "default": False,
            },
        },
        "required": ["id_field"],
    }

    async def execute(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        from app.models.polling_snapshot import PollingSnapshot

        id_field = str(config.get("id_field", "ID"))
        input_key = str(config.get("input_key", "") or "")
        emit_on_first = bool(config.get("emit_on_first_run", False))

        items = _resolve_items(inputs, input_key)
        current_ids = [
            str(item.get(id_field))
            for item in items
            if isinstance(item, dict) and item.get(id_field) is not None
        ]

        node_id = context.current_node_id or "unknown"
        snap = (
            context.db.query(PollingSnapshot)
            .filter_by(workflow_id=context.workflow_id, node_id=node_id)
            .one_or_none()
        )

        first_run = snap is None
        prev_ids: set[str] = set(snap.last_seen_ids) if snap else set()

        if first_run and not emit_on_first:
            new_items: list[dict] = []
        else:
            new_items = [
                item
                for item in items
                if isinstance(item, dict)
                and item.get(id_field) is not None
                and str(item.get(id_field)) not in prev_ids
            ]

        # Merge current + prev, then cap to avoid unbounded growth.
        merged_ids = list(prev_ids | set(current_ids))
        if len(merged_ids) > _MAX_REMEMBERED_IDS:
            merged_ids = merged_ids[-_MAX_REMEMBERED_IDS:]

        if snap is None:
            snap = PollingSnapshot(
                workflow_id=context.workflow_id,
                node_id=node_id,
                last_seen_ids=merged_ids,
            )
            context.db.add(snap)
        else:
            snap.last_seen_ids = merged_ids
            snap.updated_at = datetime.utcnow()
        context.db.commit()

        return {
            "new_items": new_items,
            "count": len(new_items),
            "total_seen": len(current_ids),
            "first_run": first_run,
        }
