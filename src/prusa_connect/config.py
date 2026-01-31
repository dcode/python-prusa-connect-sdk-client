from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    prusa_email: Optional[str] = None
    prusa_password: Optional[str] = None
    tokens_file: Path = Path("prusa_tokens.json")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
