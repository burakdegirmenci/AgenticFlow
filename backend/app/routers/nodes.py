"""Node catalog API - returns all registered node types."""

from fastapi import APIRouter

from app.nodes import NODE_REGISTRY, get_catalog

router = APIRouter()


@router.get("")
def list_nodes():
    """Return the full node catalog."""
    return get_catalog()


@router.get("/{type_id}")
def get_node(type_id: str):
    cls = NODE_REGISTRY.get(type_id)
    if cls is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"Node type {type_id} not found")
    return cls.to_catalog_entry()
