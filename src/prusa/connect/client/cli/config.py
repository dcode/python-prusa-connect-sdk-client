"""Configuration handling for the CLI."""

import json
import pathlib
import typing

import platformdirs
import structlog

try:
    import pydantic
    import pydantic_settings
except ImportError as err:
    raise ImportError(
        "The 'cli' extra is required for this feature. Install it with: pip install prusa.connect.client.cli]"
    ) from err

from prusa.connect.client import auth
from prusa.connect.client import consts as sdk_consts
from prusa.connect.client.cli import consts

logger = structlog.get_logger(sdk_consts.APP_NAME)


def load_json_config() -> dict[str, typing.Any]:
    """Load configuration from config.json."""
    config_dir = pathlib.Path(platformdirs.user_config_dir(sdk_consts.APP_NAME, sdk_consts.APP_AUTHOR))
    config_file = config_dir / "config.json"
    logger.info("Attempting to load config.json", config_file=config_file)
    if config_file.exists():
        try:
            with config_file.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            # Fallback if JSON is malformed
            logger.exception("Failed to read config.json", config_file=config_file)
            return {}
    logger.info("No config.json found.")
    return {}


class Settings(pydantic_settings.BaseSettings):
    """Application-wide settings loaded from config.json, .env or environment variables."""

    prusa_email: str | None = None
    prusa_password: pydantic.SecretStr | None = None

    default_printer_id: str | None = None
    default_team_id: int | None = None
    default_camera_id: str | None = None

    tokens_file: pathlib.Path = pydantic.Field(default_factory=auth.get_default_token_path)
    cache_ttl_hours: int = consts.DEFAULT_CACHE_TTL_HOURS

    model_config = pydantic_settings.SettingsConfigDict(env_file=".env", extra="ignore")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[pydantic_settings.BaseSettings],
        init_settings: pydantic_settings.PydanticBaseSettingsSource,
        env_settings: pydantic_settings.PydanticBaseSettingsSource,
        dotenv_settings: pydantic_settings.PydanticBaseSettingsSource,
        file_secret_settings: pydantic_settings.PydanticBaseSettingsSource,
    ) -> tuple[pydantic_settings.PydanticBaseSettingsSource, ...]:
        """Customise settings sources to include config.json."""
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            pydantic_settings.InitSettingsSource(settings_cls, load_json_config()),
            file_secret_settings,
        )


def save_json_config(current_settings: Settings) -> None:
    """Save the current configuration to config.json."""
    config_dir = pathlib.Path(platformdirs.user_config_dir(sdk_consts.APP_NAME, sdk_consts.APP_AUTHOR))
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.json"

    save_data = load_json_config()
    if current_settings.default_printer_id is not None:
        save_data["default_printer_id"] = current_settings.default_printer_id
    if current_settings.default_team_id is not None:
        save_data["default_team_id"] = current_settings.default_team_id
    if getattr(current_settings, "default_camera_id", None) is not None:
        save_data["default_camera_id"] = current_settings.default_camera_id

    with config_file.open("w", encoding="utf-8") as f:
        json.dump(save_data, f, indent=4)


if typing.TYPE_CHECKING:
    settings: Settings

_settings: Settings | None = None


def __getattr__(name: str) -> typing.Any:
    """Implement lazy loading for settings to allow logging initialization first."""
    if name == "settings":
        global _settings
        if _settings is None:
            _settings = Settings()
        return _settings
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
