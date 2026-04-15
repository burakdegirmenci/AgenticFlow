"""BaseNode abstract class - all workflow nodes inherit from this."""

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from app.engine.context import ExecutionContext


class BaseNode(ABC):
    """Abstract base for all workflow nodes.

    Each node subclass defines its type_id, category, schemas, and execute().
    Nodes are registered in app.nodes.NODE_REGISTRY via the register decorator.
    """

    # Identity
    type_id: ClassVar[str]  # "ticimax.urun.select"
    category: ClassVar[str]  # "trigger"|"ticimax"|"transform"|"logic"|"ai"|"output"
    display_name: ClassVar[str]  # "Ürün Listele"
    description: ClassVar[str] = ""  # Short help text
    icon: ClassVar[str] = "box"  # lucide-react icon name
    color: ClassVar[str] = "#6b7280"  # Hex color

    # JSON Schema definitions
    input_schema: ClassVar[dict] = {"type": "object", "properties": {}}
    output_schema: ClassVar[dict] = {"type": "object", "properties": {}}
    config_schema: ClassVar[dict] = {"type": "object", "properties": {}}

    @abstractmethod
    async def execute(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute this node and return its output as a dict."""
        ...

    @classmethod
    def to_catalog_entry(cls) -> dict:
        """Serialize class metadata for the /api/nodes catalog response."""
        return {
            "type_id": cls.type_id,
            "category": cls.category,
            "display_name": cls.display_name,
            "description": cls.description,
            "icon": cls.icon,
            "color": cls.color,
            "input_schema": cls.input_schema,
            "output_schema": cls.output_schema,
            "config_schema": cls.config_schema,
        }
