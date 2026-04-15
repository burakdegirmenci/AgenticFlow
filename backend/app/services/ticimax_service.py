"""Multi-site TicimaxClient cache and factory fix wrapper.

Imports TicimaxClient directly from the skill path (same pattern as
ProductDetail/worker/worker.py). No MCP protocol hop.
"""
import os
import sys
from typing import Any

from sqlalchemy.orm import Session

from app.models.site import Site
from app.services.crypto_service import CryptoService
from app.utils.zeep_helpers import fix_factories


# --- Add skill scripts to sys.path (same as worker.py:28-32) -------------
SKILL_SCRIPTS = os.path.join(
    os.path.expanduser("~"), ".claude", "skills", "ticimax-soap", "scripts"
)
if SKILL_SCRIPTS not in sys.path:
    sys.path.insert(0, SKILL_SCRIPTS)

try:
    from ticimax_client import TicimaxClient  # type: ignore
except ImportError as e:
    raise ImportError(
        f"Cannot import TicimaxClient from {SKILL_SCRIPTS}. "
        f"Ensure ticimax-soap skill is installed. Original: {e}"
    )


class TicimaxService:
    """Cached multi-site TicimaxClient provider."""

    _clients: dict[int, TicimaxClient] = {}

    @classmethod
    def get_client(cls, site: Site) -> TicimaxClient:
        if site.id in cls._clients:
            return cls._clients[site.id]

        uye_kodu = CryptoService.decrypt(site.uye_kodu_encrypted)
        client = TicimaxClient(domain=site.domain, uye_kodu=uye_kodu)
        fix_factories(client)
        cls._clients[site.id] = client
        return client

    @classmethod
    def invalidate(cls, site_id: int) -> None:
        cls._clients.pop(site_id, None)

    @classmethod
    def get_by_id(cls, db: Session, site_id: int) -> TicimaxClient:
        site = db.query(Site).filter(Site.id == site_id).first()
        if not site:
            raise ValueError(f"Site {site_id} not found")
        return cls.get_client(site)

    @classmethod
    def test_connection(cls, site: Site) -> dict[str, Any]:
        """Test SOAP connectivity for all 4 services."""
        try:
            client = cls.get_client(site)
            result = client.test_connection()
            return {"status": "ok", "services": result}
        except Exception as e:
            return {"status": "error", "error": str(e)}
