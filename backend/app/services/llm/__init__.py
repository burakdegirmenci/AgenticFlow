"""LLM Provider abstraction.

Supports multiple backends behind a single interface:
- anthropic_api  -> Anthropic API key (recommended, full features)
- anthropic_cli  -> Claude Code CLI subprocess (subscription, limited)
- google_genai   -> Google Gemini API key (full features)

Use `get_provider(name)` to fetch a provider instance. The global default
comes from `settings.LLM_PROVIDER` but individual chat/node calls may
override it.
"""

from __future__ import annotations

from app.services.llm.base import (
    LLMEvent,
    LLMProvider,
    LLMProviderError,
    LLMResponse,
)

_PROVIDERS: dict[str, type[LLMProvider]] = {}


def register(cls: type[LLMProvider]) -> type[LLMProvider]:
    _PROVIDERS[cls.name] = cls
    return cls


def available_providers() -> list[str]:
    return sorted(_PROVIDERS.keys())


def get_provider(name: str | None = None) -> LLMProvider:
    from app.services.settings_service import get_llm_setting

    key = name or get_llm_setting("LLM_PROVIDER") or "anthropic_api"
    cls = _PROVIDERS.get(key)
    if cls is None:
        raise LLMProviderError(f"Unknown LLM provider: {key!r}. Available: {available_providers()}")
    return cls()


# --- Register implementations (import side-effects) -------------------------
from app.services.llm import (  # noqa: F401,E402
    anthropic_api,
    anthropic_cli,
    google_genai,
)

__all__ = [
    "LLMProvider",
    "LLMResponse",
    "LLMEvent",
    "LLMProviderError",
    "get_provider",
    "available_providers",
    "register",
]
