"""Application configuration — single source of truth for all runtime settings."""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or .env file.

    Attributes:
        openrouter_api_key: API key for the OpenRouter gateway.
        model_strong: Model ID for high-quality responses.
        model_fast: Model ID for fast, lightweight responses.
        llm_base_url: Base URL for the LLM API. None uses the SDK default (OpenAI).
        redis_url: Redis connection URL for session store and price cache.
        redis_session_ttl: Session key TTL in seconds (default 7 days).
        allow_origins_list: CORS allowed origins list (comma-separated string in .env).
        cookie_secure: Whether to set the Secure flag on HttpOnly cookies.
        cookie_max_age: HttpOnly cookie Max-Age in seconds (default 1 year).
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- LLM ---
    openrouter_api_key: str = ""
    model_strong: str = "anthropic/claude-sonnet-4-5"
    model_fast: str = "anthropic/claude-haiku-4-5"
    llm_base_url: str | None = None

    # --- Financial calculation ---
    standard_variable_rate: float = 6.30
    default_loan_term: int = 30
    borrowing_capacity_dti: float = 0.28
    domain_api_key: str = ""
    budget_gap_threshold: float = 0.15

    # --- Database ---
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/propertyai"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379"
    redis_session_ttl: int = 604800

    # --- CORS ---
    allow_origins_list: list[str] = ["http://localhost:3000"]

    # --- Cookie ---
    cookie_secure: bool = True
    cookie_max_age: int = 31_536_000

    @field_validator("allow_origins_list", mode="before")
    @classmethod
    def _parse_origins(cls, v: object) -> object:
        """Support comma-separated origin strings from .env files."""
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @field_validator("database_url", mode="before")
    @classmethod
    def _ensure_asyncpg_prefix(cls, v: object) -> object:
        """Auto-convert postgresql:// DSNs to the asyncpg driver prefix."""
        if isinstance(v, str) and v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @field_validator("llm_base_url", mode="before")
    @classmethod
    def _empty_str_to_none(cls, v: object) -> object:
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


settings = Settings()
