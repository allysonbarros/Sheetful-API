"""
Application configuration settings.

This module handles all environment variables and configuration
for the Sheetful API application.
"""

import os
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    """Application settings configuration."""
    
    # Google API Settings
    GOOGLE_API_KEY: Optional[str] = os.getenv("GOOGLE_API_KEY")
    GOOGLE_SERVICE_ACCOUNT_KEY: Optional[str] = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY")
    
    # Server Settings
    PORT: int = int(os.getenv("PORT", 8000))
    HOST: str = os.getenv("HOST", "0.0.0.0")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # API Settings
    API_TITLE: str = "Sheetful API"
    API_DESCRIPTION: str = "The easiest way to turn your Google Sheet into a RESTful API"
    API_VERSION: str = "0.1.0"
    
    # CORS Settings
    ALLOWED_ORIGINS: list = ["*"]  # Configure this for production
    
    # Logging Settings
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    def validate_config(self) -> None:
        """Validate required configuration settings."""
        if not self.GOOGLE_API_KEY and not self.GOOGLE_SERVICE_ACCOUNT_KEY:
            raise ValueError(
                "Either GOOGLE_API_KEY or GOOGLE_SERVICE_ACCOUNT_KEY must be provided"
            )


# Global settings instance
settings = Settings()
