"""Printer models for Prusa Connect SDK."""

import datetime
import typing
import uuid as uuid_pkg
from enum import StrEnum

import pydantic

from .cameras import Camera
from .common import NetworkInfo, Owner, WarnExtraFieldsModel
from .jobs import JobInfo


class PrinterState(StrEnum):
    """Enum representing the possible states of a printer."""

    READY = "READY"
    IDLE = "IDLE"

    BUSY = "BUSY"
    MANIPULATING = "MANIPULATING"
    PRINTING = "PRINTING"

    PAUSED = "PAUSED"
    FINISHED = "FINISHED"
    STOPPED = "STOPPED"

    ATTENTION = "ATTENTION"
    ERROR = "ERROR"
    OFFLINE = "OFFLINE"

    # Fallback for unknown states
    UNKNOWN = "UNKNOWN"

    @classmethod
    def _missing_(cls, value: object) -> typing.Any:
        return cls.UNKNOWN


class PrinterCommand(StrEnum):
    """Enum representing known commands for a printer.

    NOTE: These commands are the subset of commands on a
    MK4S printer that do not require any additional parameters.

    TODO(dcode): Add support for commands that require additional parameters.
    TODO(dcode): Consider dynamic command generation from the printer's capabilities.
    """

    SET_PRINTER_READY = "SET_PRINTER_READY"
    CANCEL_PRINTER_READY = "CANCEL_PRINTER_READY"
    PAUSE_PRINT = "PAUSE_PRINT"
    RESUME_PRINT = "RESUME_PRINT"
    STOP_PRINT = "STOP_PRINT"
    RESET_PRINTER = "RESET_PRINTER"
    UNLOAD_FILAMENT = "UNLOAD_FILAMENT"
    SEND_INFO = "SEND_INFO"
    STOP_TRANSFER = "STOP_TRANSFER"
    SEND_STATE_INFO = "SEND_STATE_INFO"
    RESET = "RESET"
    DISABLE_STEPPERS = "DISABLE_STEPPERS"
    BEEP = "BEEP"
    # Fallback for unknown states
    UNKNOWN = "UNKNOWN"

    @classmethod
    def _missing_(cls, value: object) -> typing.Any:
        return cls.UNKNOWN


class Temperatures(WarnExtraFieldsModel):
    """Printer temperatures."""

    temp_nozzle: float | None = None
    temp_bed: float | None = None
    target_nozzle: float | None = None
    target_bed: float | None = None


class FirmwareSupport(WarnExtraFieldsModel):
    """Firmware version information."""

    latest: str | None = None
    current: str | None = None
    release_url: str | None = None
    stable: str | None = None
    prerelease: str | None = None
    release: str | None = None
    state: str | None = None


class Tool(WarnExtraFieldsModel):
    """Tool/Head information."""

    material: str | None = None
    temp: float | None = None
    nozzle_diameter: float | None = None
    fan_hotend: float | None = None
    fan_print: float | None = None
    mmu: dict[str, typing.Any] | None = None
    hardened: bool | None = None
    high_flow: bool | None = None
    active: bool | None = None


class SlotInfo(WarnExtraFieldsModel):
    """MMU Slot information."""

    active: int | None = None
    slots: dict[str, Tool] | None = None
    state: str | None = None
    command: str | None = None


class Printer(WarnExtraFieldsModel):
    """Detailed Printer Object.

    Matches structure in `printers.error.response.json` and `printer_details.json`.
    """

    uuid: str | None = None  # UUID might not be in the detail root, but often is
    name: str | None = None
    printer_state: PrinterState | None = pydantic.Field(
        None, validation_alias=pydantic.AliasChoices("printer_state", "state")
    )  # API uses 'state' or 'printer_state'
    disabled: dict[str, bool] | None = None
    printer_model: str | None = None
    firmware_version: str | None = pydantic.Field(None, alias="firmware")
    last_online: float | None = None

    network_info: NetworkInfo | None = None

    support: FirmwareSupport | None = None
    tools: dict[str, Tool] | None = None
    slot: SlotInfo | None = None
    location: str | None = None
    team_name: str | None = None
    appendix: bool | None = None
    state: PrinterState | None = None
    state_reason: str | None = None
    time_delta: int | None = None
    prusalink_api_key: pydantic.SecretStr | None = None
    api_key: pydantic.SecretStr | None = None
    sheet_settings: typing.Any | None = None
    inaccurate_estimates: bool | None = None
    enclosure: typing.Any | None = None
    slots: int | None = None
    mmu: dict[str, typing.Any] | None = None
    supported_printer_models: list[str] | None = None
    printer_type_compatible: list[str] | None = None
    connect_state: str | None = None
    allowed_functionalities: list[str] | None = None
    decision_maker: typing.Any | None = None
    printer_type: str | None = None
    fw_printer_type: str | None = None
    printer_type_name: str | None = None
    flags: dict[str, typing.Any] | None = None
    max_filename: int | None = None
    printable_extension: list[str] | None = None
    created: datetime.datetime | None = None
    sn: str | None = None
    team_id: int | None = None
    is_beta: bool | None = None
    filament: dict[str, typing.Any] | None = None
    organization_id: uuid_pkg.UUID | None = None
    rights_r: bool | None = None
    rights_w: bool | None = None
    rights_u: bool | None = None
    prusaconnect_api_key: pydantic.SecretStr | None = None
    groups: list[typing.Any] | None = None
    owner: Owner | None = None

    # Nested info
    telemetry: Temperatures | None = pydantic.Field(None, alias="temp")
    job: JobInfo | None = pydantic.Field(None, alias="job_info")
    cameras: list[Camera] | None = None

    # Capabilities
    nozzle_diameter: float | None = None
    speed: int | None = None
    flow: int | None = None
    axis_x: float | None = None
    axis_y: float | None = None
    axis_z: float | None = None

    model_config = pydantic.ConfigDict(extra="allow")


class PrinterListResponse(WarnExtraFieldsModel):
    """Response model for the /printers endpoint."""

    printers: list[Printer]
