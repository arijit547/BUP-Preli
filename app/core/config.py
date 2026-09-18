"""Application settings loaded via environment variables."""

from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # LLM Configuration
    # Supported: 'openai' (default), 'gemini', 'ollama', 'mock' (strictly testing only)
    LLM_PROVIDER: Literal["openai", "gemini", "ollama", "mock"] = "openai"
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = ""  # Optional custom base URL (e.g. for Groq, DeepSeek, Together, vLLM)
    LLM_TIMEOUT_SEC: float = 15.0
    LLM_MAX_RETRIES: int = 2

    # Server configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    # Cache configuration
    CACHE_SIZE: int = 256
    CACHE_TTL_SEC: int = 1800


settings = Settings()
