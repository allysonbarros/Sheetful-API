"""
Application configuration settings.

Uses ``pydantic-settings`` to load env vars (and ``.env``) with full type
validation. Field names are uppercase to match the existing call sites in
the codebase; env var lookups are case-insensitive.
"""

from typing import List, Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, populated from environment variables / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Google API Settings
    GOOGLE_API_KEY: Optional[str] = None
    GOOGLE_SERVICE_ACCOUNT_KEY: Optional[str] = None

    # Server Settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False

    # API Settings
    API_TITLE: str = "Sheetful API"
    API_DESCRIPTION: str = (
        "The easiest way to turn your Google Sheet into a RESTful API"
    )
    API_VERSION: str = "0.1.0"

    # CORS Settings
    ALLOWED_ORIGINS: List[str] = Field(default_factory=list)
    ALLOW_CREDENTIALS: bool = False

    # Logging Settings
    LOG_LEVEL: str = "INFO"

    @model_validator(mode="after")
    def _validate(self) -> "Settings":
        if not self.GOOGLE_API_KEY and not self.GOOGLE_SERVICE_ACCOUNT_KEY:
            raise ValueError(
                "Either GOOGLE_API_KEY or GOOGLE_SERVICE_ACCOUNT_KEY must be provided"
            )
        if self.ALLOW_CREDENTIALS and "*" in self.ALLOWED_ORIGINS:
            raise ValueError(
                "ALLOWED_ORIGINS cannot contain '*' when ALLOW_CREDENTIALS is true"
            )
        return self

    def validate_config(self) -> None:
        """Backwards-compatible no-op; validation happens at instantiation."""
        return None


def get_settings() -> Settings:
    """Factory so tests can override via ``app.dependency_overrides``."""
    return Settings()


# Module-level instance preserved for existing callers that still do
# ``from app.config import settings``.
settings = get_settings()
