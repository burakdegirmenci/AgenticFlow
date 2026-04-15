"""Multi-site TicimaxClient cache and factory fix wrapper.

TicimaxClient ships from the local `ticimax-soap` Claude Code skill, which
lives at `~/.claude/skills/ticimax-soap/scripts/`. The import is deferred to
runtime so this module can load (and tests can collect) in environments
where the skill isn't installed — for example, GitHub Actions runners.

Attempts to actually USE the client without the skill installed raise a
clear `TicimaxClientUnavailable` error pointing the user at installation
steps.
"""

from __future__ import annotations

import os
import sys
from typing import Any

from sqlalchemy.orm import Session

from app.models.site import Site
from app.services.crypto_service import CryptoService
from app.utils.zeep_helpers import fix_factories

# Note: the real `TicimaxClient` type lives in the local `ticimax-soap` Claude
# Code skill (see `_load_ticimax_client()` below). We intentionally do not
# import it at the top level — the skill is not available in CI, and pulling
# it in would break test collection. Methods annotate the returned client as
# `Any` to keep the type surface honest without a hard dependency.


def _resolve_skill_path() -> str:
    """Find the ticimax-soap skill's script directory.

    Search order:
      1. ``TICIMAX_SKILL_PATH`` env — explicit override (CI, tests, vendored).
      2. ``/skill/ticimax-soap`` — the volume-mount inside the Docker image
         (see docker-compose.yml). First choice in production.
      3. ``~/.claude/skills/ticimax-soap/scripts`` — default location on a
         developer workstation with the Claude Code skill installed.
    """
    explicit = os.environ.get("TICIMAX_SKILL_PATH")
    if explicit and os.path.isdir(explicit):
        return explicit
    in_container = "/skill/ticimax-soap"
    if os.path.isdir(in_container):
        return in_container
    return os.path.join(
        os.path.expanduser("~"), ".claude", "skills", "ticimax-soap", "scripts"
    )


_SKILL_SCRIPTS = _resolve_skill_path()


class TicimaxClientUnavailable(RuntimeError):
    """Raised when TicimaxClient cannot be imported at call time."""


def _load_ticimax_client() -> type:
    """Lazy import of TicimaxClient from the installed skill path.

    Called the first time any caller actually needs a client. Keeps module
    import side-effect free so tests that don't touch SOAP can still run.
    """
    if _SKILL_SCRIPTS not in sys.path:
        sys.path.insert(0, _SKILL_SCRIPTS)
    try:
        from ticimax_client import TicimaxClient  # type: ignore[import-not-found]

        return TicimaxClient
    except ImportError as e:  # pragma: no cover - env-dependent
        raise TicimaxClientUnavailable(
            f"Cannot import TicimaxClient from {_SKILL_SCRIPTS}. "
            "Install the `ticimax-soap` Claude Code skill "
            "(ticimax_client.py must live there). "
            f"Original import error: {e}"
        ) from e


class TicimaxService:
    """Cached multi-site TicimaxClient provider."""

    _clients: dict[int, Any] = {}

    @classmethod
    def get_client(cls, site: Site) -> Any:
        if site.id in cls._clients:
            return cls._clients[site.id]

        ticimax_client_cls = _load_ticimax_client()
        uye_kodu = CryptoService.decrypt(site.uye_kodu_encrypted)
        client = ticimax_client_cls(domain=site.domain, uye_kodu=uye_kodu)
        fix_factories(client)
        cls._clients[site.id] = client
        return client

    @classmethod
    def invalidate(cls, site_id: int) -> None:
        cls._clients.pop(site_id, None)

    @classmethod
    def get_by_id(cls, db: Session, site_id: int) -> Any:
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
