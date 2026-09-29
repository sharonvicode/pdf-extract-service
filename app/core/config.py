"""Application configuration loaded from environment variables."""
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the Extractor microservice."""

    # extra="ignore": the shared .env also holds variables for Docker Compose (e.g. PORT).
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "extractor-service"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"

    max_file_size_mb: int = 10

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (single source of truth per process)."""
    return Settings()
