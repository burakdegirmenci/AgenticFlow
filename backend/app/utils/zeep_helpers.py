"""Zeep namespace factory fix - ported from ProductDetail/worker/worker.py.

Ticimax SOAP responses use DataContract namespace that zeep doesn't resolve
by default. We try several candidate namespaces and pick the one that works
for each service's main filter type.

Also re-exports serialize_zeep_object from the ticimax-soap skill so generated
nodes can serialize SOAP responses without importing the skill path directly.
"""
import os
import sys
from typing import Any

# Ensure skill path is importable (TicimaxService also does this, but node
# modules may import zeep_helpers before TicimaxService runs).
SKILL_SCRIPTS = os.path.join(
    os.path.expanduser("~"), ".claude", "skills", "ticimax-soap", "scripts"
)
if os.path.isdir(SKILL_SCRIPTS) and SKILL_SCRIPTS not in sys.path:
    sys.path.insert(0, SKILL_SCRIPTS)

try:
    from ticimax_client import serialize_zeep_object as _sz  # type: ignore
except Exception:  # pragma: no cover - skill not available
    _sz = None


def serialize(obj: Any) -> Any:
    """Serialize a zeep response (list, dict, or scalar) to plain Python types.

    Mirrors server.py's `_serialize` helper: returns [] for None, applies
    `serialize_zeep_object` to lists element-wise, else returns a single dict.
    """
    if obj is None:
        return []
    if _sz is None:
        return obj
    result = _sz(obj)
    if isinstance(result, list):
        return [_sz(item) for item in obj]
    return result


DC_NS = "http://schemas.datacontract.org/2004/07/"


def fix_factories(client: Any) -> None:
    """Patch TicimaxClient._factories with the correct namespace factory.

    Must be called once after TicimaxClient construction, before any SOAP call.
    """
    # Lazy import - TicimaxClient comes from skill path, patched at startup
    TicimaxClientCls = type(client)

    for svc_name in TicimaxClientCls.WSDL_PATHS:
        zeep_client = client._get_client(svc_name)
        for candidate in (DC_NS, "ns2", "ns3", "ns4", "ns5"):
            try:
                factory = zeep_client.type_factory(candidate)
                # Validation probes - if these succeed, factory is good
                validators = {
                    "uye": lambda f: f.UyeFiltre(UyeID=-1),
                    "siparis": lambda f: f.WebSiparisFiltre(SiparisID=-1),
                    "urun": lambda f: f.UrunFiltre(UrunKartiID=-1),
                    "custom": lambda f: f.ServisGetSupportTicketsRequest(),
                }
                validators.get(svc_name, lambda f: None)(factory)
                client._factories[svc_name] = factory
                break
            except Exception:
                continue
