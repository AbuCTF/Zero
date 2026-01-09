"""
ZeroPool Configuration

All configuration is loaded from environment variables with sensible defaults.
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # Application
    # -------------------------------------------------------------------------
    app_name: str = "ZeroPool"
    app_env: str = "development"
    debug: bool = False
    secret_key: str = Field(..., min_length=32)
    app_url: str = "http://localhost:3000"
    api_url: str = "http://localhost:8000"

    # -------------------------------------------------------------------------
    # Database
    # -------------------------------------------------------------------------
    database_url: str = Field(
        default="postgresql+asyncpg://zeropool:zeropool@localhost:5432/zeropool"
    )

    @property
    def database_url_sync(self) -> str:
        """Synchronous database URL for Alembic migrations."""
        return self.database_url.replace("+asyncpg", "")

    # -------------------------------------------------------------------------
    # Redis
    # -------------------------------------------------------------------------
    redis_url: str = "redis://localhost:6379/0"

    # -------------------------------------------------------------------------
    # Session
    # -------------------------------------------------------------------------
    session_lifetime_hours: int = 24
    session_cookie_name: str = "zeropool_session"
    session_cookie_secure: bool = False
    session_cookie_httponly: bool = True
    session_cookie_samesite: str = "lax"

    # -------------------------------------------------------------------------
    # Security
    # -------------------------------------------------------------------------
    password_hash_method: str = "pbkdf2:sha256"
    password_hash_iterations: int = 600000
    rate_limit_per_minute: int = 60
    rate_limit_per_hour: int = 1000
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 15

    # -------------------------------------------------------------------------
    # Cloudflare Turnstile
    # -------------------------------------------------------------------------
    turnstile_site_key: Optional[str] = None
    turnstile_secret_key: Optional[str] = None

    @property
    def turnstile_enabled(self) -> bool:
        return bool(self.turnstile_site_key and self.turnstile_secret_key)

    # -------------------------------------------------------------------------
    # Certificates
    # -------------------------------------------------------------------------
    cert_salt: str = Field(default="change-this-salt")
    fonts_dir: str = "/app/fonts"
    certs_dir: str = "/app/storage/certificates"

    # -------------------------------------------------------------------------
    # File Storage
    # -------------------------------------------------------------------------
    upload_dir: str = "/app/storage/uploads"
    max_upload_size_mb: int = 10

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    # -------------------------------------------------------------------------
    # Encryption
    # -------------------------------------------------------------------------
    encryption_key: Optional[str] = None

    # -------------------------------------------------------------------------
    # Email Defaults
    # -------------------------------------------------------------------------
    email_from_name: str = "ZeroPool"
    email_from_address: str = "noreply@example.com"

    # -------------------------------------------------------------------------
    # Admin Bootstrap
    # -------------------------------------------------------------------------
    admin_email: str = "admin@example.com"
    admin_username: str = "admin"
    admin_password: str = "changeme123"

    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------
    log_level: str = "INFO"
    log_format: str = "json"

    # -------------------------------------------------------------------------
    # CORS
    # -------------------------------------------------------------------------
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return v.upper()


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Uses lru_cache to ensure settings are only loaded once.
    """
    return Settings()
