from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    prusa_email: str | None = None
    prusa_password: str | None = None
    tokens_file: Path = Path("prusa_tokens.json")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
