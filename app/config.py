"""Application configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Keys
    anthropic_api_key: str

    # Database
    database_url: str = "sqlite+aiosqlite:///./coaching.db"

    # Application Settings
    debug: bool = False
    default_max_turns: int = 12
    min_max_turns: int = 4
    max_max_turns: int = 20

    # LLM Settings
    model_name: str = "claude-sonnet-4-20250514"
    temperature: float = 0.7
    max_tokens: int = 1024

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
