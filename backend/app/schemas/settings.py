"""Pydantic schemas for the settings API."""
from pydantic import BaseModel, Field


class LLMSettingsOut(BaseModel):
    """Effective LLM settings — secrets masked for safe display."""

    LLM_PROVIDER: str
    ANTHROPIC_API_KEY_masked: str
    ANTHROPIC_API_KEY_set: bool
    CLAUDE_MODEL_AGENT: str
    CLAUDE_MODEL_NODE: str
    CLAUDE_CLI_PATH: str
    GOOGLE_API_KEY_masked: str
    GOOGLE_API_KEY_set: bool
    GEMINI_MODEL_AGENT: str
    GEMINI_MODEL_NODE: str


class LLMSettingsUpdate(BaseModel):
    """Partial update — only provided fields are written.

    Empty string for an API key clears the override (falls back to env).
    None means "leave alone" (Pydantic optional with default None).
    """

    LLM_PROVIDER: str | None = Field(default=None)
    ANTHROPIC_API_KEY: str | None = Field(default=None)
    CLAUDE_MODEL_AGENT: str | None = Field(default=None)
    CLAUDE_MODEL_NODE: str | None = Field(default=None)
    CLAUDE_CLI_PATH: str | None = Field(default=None)
    GOOGLE_API_KEY: str | None = Field(default=None)
    GEMINI_MODEL_AGENT: str | None = Field(default=None)
    GEMINI_MODEL_NODE: str | None = Field(default=None)


class ProviderTestResult(BaseModel):
    name: str
    display_name: str
    available: bool
    reason: str
