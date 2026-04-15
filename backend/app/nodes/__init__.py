"""Global node registry.

Nodes register themselves at import time. Importing this module populates
NODE_REGISTRY as a side-effect.
"""
from app.engine.node_base import BaseNode


NODE_REGISTRY: dict[str, type[BaseNode]] = {}


def register(node_cls: type[BaseNode]) -> type[BaseNode]:
    """Decorator that adds a node class to NODE_REGISTRY."""
    if not hasattr(node_cls, "type_id"):
        raise ValueError(f"{node_cls.__name__} missing type_id")
    NODE_REGISTRY[node_cls.type_id] = node_cls
    return node_cls


def get_catalog() -> list[dict]:
    """Return catalog entries for all registered nodes."""
    return [cls.to_catalog_entry() for cls in NODE_REGISTRY.values()]


# --- Import side effects: register all built-in nodes -----------------------
from app.nodes.triggers import manual, polling, schedule  # noqa: F401,E402
from app.nodes.ticimax import urun, siparis  # noqa: F401,E402
from app.nodes.ticimax import _auto_generated  # noqa: F401,E402
from app.nodes.ticimax import update_aciklama_batch  # noqa: F401,E402
from app.nodes.ticimax import update_ozel_alan_1_batch  # noqa: F401,E402
from app.nodes.ticimax import set_siparis_durum_batch  # noqa: F401,E402
from app.nodes.transform import (  # noqa: F401,E402
    parse_stok,
    filter as filter_node,
    map_node,
    aggregate,
    only_new,
)
from app.nodes.logic import (  # noqa: F401,E402
    if_condition,
    switch,
    loop,
)
from app.nodes.ai import (  # noqa: F401,E402
    claude_prompt,
    classify,
    extract,
    vision,
    vision_batch,
)
from app.nodes.output import (  # noqa: F401,E402
    log_node,
    csv_export,
    excel_export,
    json_export,
)
