"""Service for Printer operations."""

import json
import time
import typing
from pathlib import Path

import structlog

from prusa.connect.client import command_models, exceptions, models
from prusa.connect.client.services.base import BaseService

logger = structlog.get_logger(__name__)


class PrinterService(BaseService):
    """Service for managing printers."""

    def __init__(self, client, cache_dir: Path | None = None, cache_ttl: int = 3600):
        """Initialize the printer service."""
        super().__init__(client)
        self._cache_dir = cache_dir
        self._cache_ttl = cache_ttl
        self._supported_commands_cache: dict[str, list[command_models.CommandDefinition]] = {}

    def list_printers(self, limit: int = 100, offset: int = 0) -> list[models.Printer]:
        """Fetch all printers associated with the account."""
        cache_file = None
        if self._cache_dir:
            cache_file = self._cache_dir / "printers" / "list.json"

        try:
            params = {"limit": limit, "offset": offset}
            data = self._client.request("GET", "/app/printers", params=params)

            parsed_printers = []
            if isinstance(data, dict) and "printers" in data:
                parsed_printers = [models.Printer.model_validate(p) for p in data["printers"]]
            elif isinstance(data, list):
                parsed_printers = [models.Printer.model_validate(p) for p in data]
            else:
                logger.warning("Unexpected printer response format", data=data)

            if cache_file and parsed_printers:
                try:
                    cache_file.parent.mkdir(parents=True, exist_ok=True)
                    cache_data = {"printers": [p.model_dump(mode="json") for p in parsed_printers]}
                    cache_file.write_text(json.dumps(cache_data, indent=2))
                except Exception as e:
                    logger.warning("Failed to save printers to cache", error=str(e))

            return parsed_printers

        except Exception as e:
            if cache_file and cache_file.exists():
                try:
                    mtime = cache_file.stat().st_mtime
                    age = time.time() - mtime
                    if age > self._cache_ttl:
                        logger.warning("Cached printer list expired", age=age, ttl=self._cache_ttl)
                        raise exceptions.PrusaAuthError("Cache expired and network failed.")

                    logger.info("Using cached printer list due to error", error=str(e))
                    data = json.loads(cache_file.read_text())
                    if isinstance(data, dict) and "printers" in data:
                        return [models.Printer.model_validate(p) for p in data["printers"]]
                except Exception as cache_e:
                    logger.warning("Failed to load cached printers", error=str(cache_e))
            raise e

    def get(self, uuid: str) -> models.Printer:
        """Fetch details for a specific printer."""
        data = self._client.request("GET", f"/app/printers/{uuid}")
        return models.Printer.model_validate(data)

    def send_command(self, uuid: str, command: str, kwargs: dict | None = None) -> bool:
        """Send a command to a printer."""
        payload: dict[str, typing.Any] = {"command": command}
        if kwargs:
            payload["kwargs"] = kwargs
        self._client.request("POST", f"/app/printers/{uuid}/commands/sync", json=payload)
        return True

    def get_supported_commands(self, uuid: str) -> list[command_models.CommandDefinition]:
        """Fetch supported commands for a printer."""
        if uuid in self._supported_commands_cache:
            return self._supported_commands_cache[uuid]

        cache_file = None
        if self._cache_dir:
            cache_file = self._cache_dir / "printers" / uuid / "commands.json"
            if cache_file.exists():
                try:
                    data = json.loads(cache_file.read_text())
                    cmds = [command_models.CommandDefinition.model_validate(c) for c in data]
                    self._supported_commands_cache[uuid] = cmds
                    return cmds
                except Exception as e:
                    logger.warning("Failed to load cached commands", error=str(e))

        data = self._client.request("GET", f"/app/printers/{uuid}/commands")
        if isinstance(data, dict):
            # Try to handle varying implementations format
            potential_lists = [v for v in data.values() if isinstance(v, list)]
            raw_cmds = potential_lists[0] if potential_lists else []
        elif isinstance(data, list):
            raw_cmds = data
        else:
            raw_cmds = []

        cmds = [command_models.CommandDefinition.model_validate(c) for c in raw_cmds]
        self._supported_commands_cache[uuid] = cmds

        if cache_file:
            try:
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.write_text(json.dumps([c.model_dump(mode="json") for c in cmds], indent=2))
            except Exception as e:
                logger.warning("Failed to save commands cache", error=str(e))

        # Compatibility Check
        # We require at least STOP_PRINT to be supported to ensure safe operation
        required_commands = {"STOP_PRINT"}
        supported_command_names = {c.command for c in cmds}
        missing_commands = required_commands - supported_command_names

        if missing_commands:
            logger.error("Printer missing required commands", missing=missing_commands, uuid=uuid)
            try:
                printer = self.get(uuid)
                printer_data = printer.model_dump(mode="json")
                # Redact sensitive info
                for field in ["uuid", "name", "serial", "ip", "mac"]:
                    if field in printer_data:
                        printer_data[field] = "[REDACTED]"
            except Exception as e:
                logger.warning("Failed to fetch printer details for error report", error=str(e))
                printer_data = {"error": "Failed to fetch details"}

            raise exceptions.PrusaCompatibilityError(
                f"Printer {uuid} is missing required commands: {missing_commands}",
                missing_commands=list(missing_commands),
                report_data={"printer_details": printer_data},
            )

        return cmds
