"""Application configuration — single source of truth for all runtime settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or .env file.

    Attributes:
        openrouter_api_key: API key for the OpenRouter gateway.
        model_strong: Model ID for high-quality responses.
        model_fast: Model ID for fast, lightweight responses.
    """

    model_config = SettingsConfigDict(env_file=".env")

    openrouter_api_key: str = ""
    model_strong: str = "anthropic/claude-sonnet-4-5"
    model_fast: str = "anthropic/claude-haiku-4-5"


settings = Settings()
