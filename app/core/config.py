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
    LLM_MODEL: str = "gpt-5.6-terra"
    LLM_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = ""
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

    def get_effective_api_key(self) -> str:
        return self.LLM_API_KEY or self.OPENAI_API_KEY

    def get_effective_model(self) -> str:
        return self.OPENAI_MODEL or self.LLM_MODEL


settings = Settings()
if not settings.LLM_API_KEY and settings.OPENAI_API_KEY:
    settings.LLM_API_KEY = settings.OPENAI_API_KEY
if settings.OPENAI_MODEL:
    settings.LLM_MODEL = settings.OPENAI_MODEL

