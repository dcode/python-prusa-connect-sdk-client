"""Configuration settings for Prusa Connect application."""

from pathlib import Path

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError as err:
    raise ImportError(
        "The 'cli' extra is required for this feature. Install it with: pip install prusa-connect[cli]"
    ) from err


class Settings(BaseSettings):
    """Application-wide settings loaded from .env or environment variables."""

    prusa_email: str | None = None
    prusa_password: str | None = None
    tokens_file: Path = Path("prusa_tokens.json")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
