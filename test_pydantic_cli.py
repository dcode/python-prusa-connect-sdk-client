from pydantic_settings import BaseSettings, SettingsConfigDict, CliApp
from pydantic import Field
from typing import Literal, Optional, List
import sys

try:
    from pydantic_settings import CliApp
    print("CliApp found (experimental/new feature?)")
except ImportError:
    print("CliApp NOT found")

class Config(BaseSettings):
    debug: bool = False
    verbose: bool = False
    command: str = "help"
    printer_id: Optional[str] = None
    
    model_config = SettingsConfigDict(cli_parse_args=True)

try:
    c = Config()
    print(f"Parsed: {c.model_dump()}")
except Exception as e:
    print(f"Error: {e}")
