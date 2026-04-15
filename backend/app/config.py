"""Application settings loaded from .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM provider selection — "anthropic_api" | "anthropic_cli" | "google_genai"
    LLM_PROVIDER: str = "anthropic_api"

    # Anthropic API (official SDK)
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL_AGENT: str = "claude-opus-4-6"
    CLAUDE_MODEL_NODE: str = "claude-sonnet-4-5-20250929"

    # Anthropic CLI (subscription via Claude Code)
    CLAUDE_CLI_PATH: str = "claude"

    # Google Gemini (google-genai SDK)
    GOOGLE_API_KEY: str = ""
    GEMINI_MODEL_AGENT: str = "gemini-2.5-pro"
    GEMINI_MODEL_NODE: str = "gemini-2.5-flash"

    # Crypto
    MASTER_KEY: str = ""

    # DB
    DATABASE_URL: str = "sqlite:///./agenticflow.db"

    # Server
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Observability
    LOG_LEVEL: str = "INFO"  # DEBUG / INFO / WARNING / ERROR
    LOG_DIR: str = "logs"  # empty string disables rotating file output
    LOG_FILE: str = "agenticflow.log"
    SENTRY_DSN: str = ""  # empty = Sentry disabled

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
