"""Settings API — read/update user-editable LLM settings, test providers."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.settings import (
    LLMSettingsOut,
    LLMSettingsUpdate,
    ProviderTestResult,
)
from app.services import settings_service
from app.services.llm import available_providers, get_provider

router = APIRouter()


def _build_out() -> LLMSettingsOut:
    eff = settings_service.get_all_effective()
    return LLMSettingsOut(
        LLM_PROVIDER=eff.get("LLM_PROVIDER", "anthropic_api") or "anthropic_api",
        ANTHROPIC_API_KEY_masked=settings_service.mask_secret(eff.get("ANTHROPIC_API_KEY", "")),
        ANTHROPIC_API_KEY_set=bool(eff.get("ANTHROPIC_API_KEY")),
        CLAUDE_MODEL_AGENT=eff.get("CLAUDE_MODEL_AGENT", ""),
        CLAUDE_MODEL_NODE=eff.get("CLAUDE_MODEL_NODE", ""),
        CLAUDE_CLI_PATH=eff.get("CLAUDE_CLI_PATH", "claude") or "claude",
        GOOGLE_API_KEY_masked=settings_service.mask_secret(eff.get("GOOGLE_API_KEY", "")),
        GOOGLE_API_KEY_set=bool(eff.get("GOOGLE_API_KEY")),
        GEMINI_MODEL_AGENT=eff.get("GEMINI_MODEL_AGENT", ""),
        GEMINI_MODEL_NODE=eff.get("GEMINI_MODEL_NODE", ""),
    )


@router.get("/llm", response_model=LLMSettingsOut)
def get_llm_settings():
    return _build_out()


@router.put("/llm", response_model=LLMSettingsOut)
def update_llm_settings(payload: LLMSettingsUpdate, db: Session = Depends(get_db)):
    # Only forward fields that were explicitly provided. None == untouched.
    incoming = {k: v for k, v in payload.model_dump().items() if v is not None}
    if incoming:
        settings_service.set_many(db, incoming)
    return _build_out()


@router.post("/llm/test", response_model=list[ProviderTestResult])
async def test_all_providers():
    """Run is_available() for every registered provider with current settings."""
    results: list[ProviderTestResult] = []
    for name in available_providers():
        try:
            p = get_provider(name)
            ok, reason = await p.is_available()
            results.append(
                ProviderTestResult(
                    name=p.name,
                    display_name=p.display_name,
                    available=ok,
                    reason=reason,
                )
            )
        except Exception as e:
            results.append(
                ProviderTestResult(
                    name=name,
                    display_name=name,
                    available=False,
                    reason=f"init error: {e}",
                )
            )
    return results
