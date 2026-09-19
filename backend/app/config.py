"""zeropool config; loaded from env vars with defaults."""

import logging
from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# known insecure placeholder values shipped in defaults / .env.example;
# warn loudly (never crash) if any are still in use at startup
_INSECURE_PLACEHOLDERS = {
    "admin_password": {"changeme123"},
    "secret_key": {"your-super-secret-key-change-this-in-production"},
    "cert_salt": {"change-this-salt", "your-certificate-salt-change-this"},
    "encryption_key": {None, "", "your-encryption-key-change-this"},
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "ZeroPool"
    app_env: str = "development"
    debug: bool = False
    secret_key: str = Field(..., min_length=32)
    app_url: str = "http://localhost:3000"
    api_url: str = "http://localhost:8000"

    database_url: str = Field(
        default="postgresql+asyncpg://zeropool:zeropool@localhost:5432/zeropool"
    )

    @property
    def database_url_sync(self) -> str:
        # sync url for alembic migrations
        return self.database_url.replace("+asyncpg", "")

    redis_url: str = "redis://localhost:6379/0"

    session_lifetime_hours: int = 24
    session_cookie_name: str = "zeropool_session"
    session_cookie_secure: bool = False
    session_cookie_httponly: bool = True
    session_cookie_samesite: str = "lax"

    password_hash_method: str = "pbkdf2:sha256"
    password_hash_iterations: int = 600000
    rate_limit_per_minute: int = 60
    rate_limit_per_hour: int = 1000
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 15

    turnstile_site_key: Optional[str] = None
    turnstile_secret_key: Optional[str] = None

    @property
    def turnstile_enabled(self) -> bool:
        return bool(self.turnstile_site_key and self.turnstile_secret_key)

    discord_client_id: str = "1547022816937771028"
    discord_client_secret: Optional[str] = None
    discord_redirect_uri: str = "https://app.h7tex.com/api/auth/discord/callback"
    discord_min_account_age_days: int = 7
    # origins allowed to open the oauth popup and receive its postmessage token
    discord_popup_origins: str = (
        "https://2026.h7tex.com,https://app.h7tex.com,http://localhost:5173,http://localhost:3000"
    )
    # when true, registration requires a valid discord verification + profile fields;
    # deploy endpoints with this false, ship the popup, verify, then flip to true
    discord_required: bool = False

    @property
    def discord_enabled(self) -> bool:
        return bool(self.discord_client_id and self.discord_client_secret)

    anvil_sso_shared_secret: Optional[str] = None
    anvil_sso_url: str = "https://ctf.h7tex.com/sso"

    @property
    def anvil_sso_enabled(self) -> bool:
        return bool(self.anvil_sso_shared_secret)

    cert_salt: str = Field(default="change-this-salt")
    fonts_dir: str = "/app/fonts"
    certs_dir: str = "/app/storage/certificates"

    upload_dir: str = "/app/storage/uploads"
    max_upload_size_mb: int = 10

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    encryption_key: Optional[str] = None

    email_from_name: str = "ZeroPool"
    email_from_address: str = "noreply@example.com"

    admin_email: str = "admin@example.com"
    admin_username: str = "admin"
    admin_password: str = "changeme123"

    log_level: str = "INFO"
    log_format: str = "json"

    cors_origins: str = "http://localhost:3000,http://localhost:5173,https://h7tex.com,https://www.h7tex.com,https://2026.h7tex.com,https://app.h7tex.com"

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


def _warn_on_insecure_defaults(settings: "Settings") -> None:
    # emit startup warning (never crash) when secrets left at placeholder/default values
    for field, placeholders in _INSECURE_PLACEHOLDERS.items():
        value = getattr(settings, field, None)
        if value in placeholders:
            logger.warning(
                "Insecure configuration: %s is set to a known placeholder/default "
                "value. Set a strong, unique value before running in production.",
                field.upper(),
            )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    _warn_on_insecure_defaults(settings)
    return settings
