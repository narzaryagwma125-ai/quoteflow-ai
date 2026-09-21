from __future__ import annotations

import sys
from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_SECRETS = {
    "replace_with_long_random_secret",
    "replace_with_long_random_secret_at_least_32_chars",
    "change_me_dev_secret",
}


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Core
    app_env: Literal["development", "test", "production"] = "development"
    secret_key: str = "dev_only_secret_key_change_this_1234567890"
    database_url: str = (
        "postgresql+asyncpg://quoteflow:quoteflow_dev_password@localhost:5432/quoteflow"
    )
    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"
    log_level: str = "INFO"

    # Sessions
    session_cookie_name: str = "quoteflow_session"
    session_cookie_secure: bool = False
    session_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    session_lifetime_days: int = 30

    # Email
    # Email delivery uses Resend HTTPS API (not SMTP).
    resend_api_key: str = ""
    resend_api_url: str = "https://api.resend.com/emails"
    email_api_timeout_seconds: float = 20.0
    email_from: str = "no-reply@quoteflow.example"
    support_email: str = "support@quoteflow.example"
    email_verification_required: bool = True

    # AI
    gemini_api_key: str = ""
    # Empty = auto-select the first model enabled for the API key that supports
    # content generation. Set a model name (e.g. "models/gemini-2.5-flash") to pin it.
    gemini_model: str = ""
    ai_models_cache_ttl_seconds: int = 300
    ai_request_timeout_seconds: int = 20

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_starter_price_id: str = ""
    stripe_pro_price_id: str = ""
    stripe_business_price_id: str = ""
    stripe_success_url: str = "http://localhost:3000/billing?checkout=success"
    stripe_cancel_url: str = "http://localhost:3000/billing?checkout=cancelled"

    # Free trial
    free_trial_enabled: bool = True
    free_trial_days: int = 5
    free_trial_unlimited: bool = False

    # Development-only: lift the monthly quote limit so the flow can be tested
    # locally. Honored ONLY when APP_ENV=development — never in production or
    # in the test suite (see services.subscription).
    dev_ignore_quote_limits: bool = False

    # Uploads
    upload_dir: str = "./uploads"
    max_logo_size_bytes: int = 2 * 1024 * 1024  # 2 MB

    @field_validator("secret_key")
    @classmethod
    def secret_key_long_enough(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return v

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_url.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def session_cookie_secure_effective(self) -> bool:
        return self.session_cookie_secure or self.is_production

    def sanitized_database_url(self) -> str:
        """Log-safe database URL with credentials redacted."""
        try:
            from urllib.parse import urlsplit, urlunsplit

            parts = urlsplit(self.database_url)
            if parts.password:
                netloc = parts.netloc.replace(f":{parts.password}@", ":***@")
                return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
        except Exception:
            pass
        return "<database-url>"

    def validate_production(self) -> None:
        """Fail fast if required production secrets are missing or placeholder values."""
        if self.app_env != "production":
            return
        required = {
            "SECRET_KEY": self.secret_key,
            "GEMINI_API_KEY": self.gemini_api_key,
            "STRIPE_SECRET_KEY": self.stripe_secret_key,
            "STRIPE_WEBHOOK_SECRET": self.stripe_webhook_secret,
            # Basic and Pro are enabled plans. Business can remain unconfigured
            # until its Stripe USD $24/month Price is created.
            "STRIPE_STARTER_PRICE_ID": self.stripe_starter_price_id,
            "STRIPE_PRO_PRICE_ID": self.stripe_pro_price_id,
        }
        if self.email_verification_required:
            required.update({
                "RESEND_API_KEY": self.resend_api_key,
                "EMAIL_FROM": self.email_from,
            })
        missing = [
            name for name, value in required.items() if not value or value in _PLACEHOLDER_SECRETS
        ]
        if missing:
            print(
                "[FATAL] Production startup aborted: missing or placeholder environment settings: "
                f"{', '.join(missing)}",
                file=sys.stderr,
            )
            raise RuntimeError("Missing required production secrets. See README.md.")

        stripe_price_ids = [
            price_id
            for price_id in (
                self.stripe_starter_price_id,
                self.stripe_pro_price_id,
                self.stripe_business_price_id,
            )
            if price_id
        ]
        if len(set(stripe_price_ids)) != len(stripe_price_ids):
            print(
                "[FATAL] Production startup aborted: Stripe Basic/Pro/Business Price IDs must be unique.",
                file=sys.stderr,
            )
            raise RuntimeError("Stripe Price IDs must be unique across all paid plans.")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_production()
    return settings


settings = get_settings()
