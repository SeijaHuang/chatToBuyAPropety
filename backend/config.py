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
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openrouter_api_key: str = ""
    model_strong: str = "anthropic/claude-sonnet-4-5"
    model_fast: str = "anthropic/claude-haiku-4-5"
    llm_base_url: str | None = None
    standard_variable_rate: float = 6.30
    default_loan_term: int = 30
    borrowing_capacity_dti: float = 0.28

    @field_validator("llm_base_url", mode="before")
    @classmethod
    def _empty_str_to_none(cls, v: object) -> object:
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


settings = Settings()
