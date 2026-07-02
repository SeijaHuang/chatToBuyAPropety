"""Unit tests for Settings configuration field validators."""

from config import Settings


def test_parse_origins_converts_comma_string_to_list() -> None:
    """_parse_origins splits a comma-separated string into a list of stripped origins."""
    s: Settings = Settings(allow_origins_list="http://localhost:3000,https://prod.example.com")  # type: ignore[arg-type]
    assert s.allow_origins_list == ["http://localhost:3000", "https://prod.example.com"]


def test_ensure_asyncpg_prefix_rewrites_postgresql_url() -> None:
    """_ensure_asyncpg_prefix replaces postgresql:// with the asyncpg driver prefix."""
    s: Settings = Settings(database_url="postgresql://user:pass@localhost:5432/db")
    assert s.database_url == "postgresql+asyncpg://user:pass@localhost:5432/db"


def test_empty_str_to_none_converts_blank_llm_base_url() -> None:
    """_empty_str_to_none converts an empty-string llm_base_url to None."""
    s: Settings = Settings(llm_base_url="")
    assert s.llm_base_url is None
