"""
API Configuration
"""

import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """API configuration from environment variables."""

    # API metadata
    app_name: str = "CollectOS API"
    app_version: str = "1.0.0"
    api_prefix: str = "/api/v1"

    # Security
    secret_key: str = os.getenv("API_SECRET_KEY", "dev_secret_key_change_in_production")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480  # 8 hours

    # CORS
    allowed_origins: List[str] = [
        "http://localhost:3000",  # React PWA dev
        "http://localhost:8501",  # Streamlit ops console
        "http://localhost:5173",  # Vite dev server
    ]

    # Database
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://collectos:collectos_dev_password_change_in_production@localhost:5432/collectos"
    )

    # Rate limiting
    rate_limit_per_minute: int = 60

    # PII masking for AUDITOR role
    mask_pii: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"  # Ignore extra fields from .env
    )


settings = Settings()
