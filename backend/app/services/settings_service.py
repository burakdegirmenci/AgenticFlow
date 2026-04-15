"""Runtime settings service.

User-editable LLM settings (provider, API keys, model overrides) live in
the `app_settings` table. Sensitive values are Fernet-encrypted with the
existing MASTER_KEY. Reads fall back to the environment-loaded
`Settings` defaults when no DB override exists.

Provider modules should call `get_llm_setting(key)` instead of reading
`Settings` attributes directly so user changes apply without restart.
"""
from __future__ import annotations

from threading import RLock
from typing import Iterable

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.models.app_setting import AppSetting
from app.services.crypto_service import CryptoService


# Keys that may be persisted via Settings UI. Anything else is rejected.
LLM_KEYS: tuple[str, ...] = (
    "LLM_PROVIDER",
    "ANTHROPIC_API_KEY",
    "CLAUDE_MODEL_AGENT",
    "CLAUDE_MODEL_NODE",
    "CLAUDE_CLI_PATH",
    "GOOGLE_API_KEY",
    "GEMINI_MODEL_AGENT",
    "GEMINI_MODEL_NODE",
)

# Keys that must always be encrypted at rest.
SECRET_KEYS: frozenset[str] = frozenset(
    {"ANTHROPIC_API_KEY", "GOOGLE_API_KEY"}
)


# ---------------------------------------------------------------------------
# In-memory cache (lock-protected). Cleared on every PUT.
# ---------------------------------------------------------------------------
_cache: dict[str, str] | None = None
_cache_lock = RLock()


def _load_overrides_locked() -> dict[str, str]:
    """Read all DB overrides into a {key: plaintext} dict."""
    db: Session = SessionLocal()
    try:
        rows: Iterable[AppSetting] = db.query(AppSetting).all()
        out: dict[str, str] = {}
        for row in rows:
            if row.key not in LLM_KEYS:
                continue
            if row.encrypted:
                if not row.value:
                    out[row.key] = ""
                    continue
                try:
                    out[row.key] = CryptoService.decrypt(row.value)
                except Exception:
                    # Bad ciphertext / wrong master key — surface as empty
                    out[row.key] = ""
            else:
                out[row.key] = row.value
        return out
    finally:
        db.close()


def _get_cache() -> dict[str, str]:
    global _cache
    with _cache_lock:
        if _cache is None:
            _cache = _load_overrides_locked()
        return _cache


def invalidate_cache() -> None:
    global _cache
    with _cache_lock:
        _cache = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def get_llm_setting(key: str) -> str:
    """Effective value: DB override → env default → empty string."""
    if key not in LLM_KEYS:
        raise KeyError(f"Unknown LLM setting key: {key!r}")
    overrides = _get_cache()
    if key in overrides and overrides[key] != "":
        return overrides[key]
    settings = get_settings()
    return getattr(settings, key, "") or ""


def get_all_effective() -> dict[str, str]:
    """Return all LLM keys with their effective values (decrypted)."""
    return {k: get_llm_setting(k) for k in LLM_KEYS}


def get_overrides() -> dict[str, str]:
    """Return only DB overrides (decrypted), without env fallback."""
    return dict(_get_cache())


def set_value(db: Session, key: str, value: str) -> None:
    """Upsert a single setting. Encrypts if key is in SECRET_KEYS."""
    if key not in LLM_KEYS:
        raise KeyError(f"Unknown LLM setting key: {key!r}")

    encrypted_flag = key in SECRET_KEYS
    stored = CryptoService.encrypt(value) if (encrypted_flag and value) else value

    row = db.query(AppSetting).filter(AppSetting.key == key).one_or_none()
    if row is None:
        row = AppSetting(key=key, value=stored, encrypted=encrypted_flag)
        db.add(row)
    else:
        row.value = stored
        row.encrypted = encrypted_flag


def set_many(db: Session, values: dict[str, str]) -> None:
    """Upsert multiple settings in one transaction."""
    for k, v in values.items():
        if k not in LLM_KEYS:
            continue
        set_value(db, k, v if v is not None else "")
    db.commit()
    invalidate_cache()


def mask_secret(value: str) -> str:
    """Mask an API key for safe display: show only first/last 4 chars."""
    if not value:
        return ""
    if len(value) <= 8:
        return "•" * len(value)
    return f"{value[:4]}{'•' * 8}{value[-4:]}"
