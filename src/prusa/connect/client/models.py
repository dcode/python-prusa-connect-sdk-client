"""Pydantic models for Prusa Connect API responses.

This module defines the data structures used by the client to parse
API responses into typed objects.

How to use the most important parts:
- Explore these models (`Printer`, `Job`, `Camera`, `File`) to understand the attributes available when
  leveraging the `PrusaConnectClient`.
- `WarnExtraFieldsModel`: Base class used to log warnings if the Prusa Connect API adds new fields not yet
  documented in this SDK.

Note:
  Models of API responses are subclassed from WarnExtraFieldsModel. If a
  response contains fields that are not present in the model, a warning will be
  logged. If the log level is set to DEBUG, the full response will be logged
  so that the user can see the extra fields and decide whether to update the
  model. Users should file an issue with this content on the GitHub repository
  if they encounter unexpected extra fields.

  Pull requests with updated models are welcome! :thumbsup:
"""

import datetime
import enum
import logging
import typing
import uuid as uuid_pkg

import pydantic

from prusa.connect.client import consts

__all__ = [
    "Camera",
    "CancelableObject",
    "File",
    "FirmwareFile",
    "FirmwareFileMeta",
    "Job",
    "JobFailureReason",
    "JobInfo",
    "Owner",
    "PrintFile",
    "PrintFileMeta",
    "PrinterState",
    "RegularFile",
    "SourceInfo",
    "Storage",
    "SyncInfo",
    "Team",
    "Temperatures",
    "UploadStatus",
]

logger = logging.getLogger(__name__)


class WarnExtraFieldsModel(pydantic.BaseModel):
    """Base model that logs a warning if extra fields are present."""

    model_config = pydantic.ConfigDict(extra="allow")

    def __init__(self, **data: typing.Any):
        super().__init__(**data)
        if self.__pydantic_extra__:
            logger.warning(
                f"Model {self.__class__.__name__} received unknown fields: {list(self.__pydantic_extra__.keys())}"
            )


class PrinterState(enum.StrEnum):
    """Enum representing the possible states of a printer."""

    IDLE = "IDLE"
    PRINTING = "PRINTING"
    ATTENTION = "ATTENTION"
    FINISHED = "FINISHED"
    STOPPED = "STOPPED"
    ERROR = "ERROR"
    READY = "READY"
    BUSY = "BUSY"
    OFFLINE = "OFFLINE"
    # Fallback for unknown states
    UNKNOWN = "UNKNOWN"

    @classmethod
    def _missing_(cls, value: object) -> typing.Any:
        return cls.UNKNOWN


class PrinterCommand(enum.StrEnum):
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


class JobFailureTag(enum.StrEnum):
    """Enum representing reasons for job failure/cancellation."""

    IGNORED = "IGNORED"
    CLOGGED_NOZZLE = "CLOGGED_NOZZLE"
    NON_ADHERENT_BED = "NON_ADHERENT_BED"
    UNDER_EXTRUSION = "UNDER_EXTRUSION"
    OVER_EXTRUSION = "OVER_EXTRUSION"
    STRINGING_OR_OOZING = "STRINGING_OR_OOZING"
    GAPS_IN_THIN_WALLS = "GAPS_IN_THIN_WALLS"
    OVERHEATING = "OVERHEATING"
    LAYER_SHIFTING = "LAYER_SHIFTING"
    SPAGHETTI_MONSTER = "SPAGHETTI_MONSTER"
    LAYER_SEPARATION = "LAYER_SEPARATION"
    WARPING = "WARPING"
    POOR_BRIDGING = "POOR_BRIDGING"
    OTHER = "OTHER"


class SourceInfo(WarnExtraFieldsModel):
    """Information about the source of an action or object (e.g., user)."""

    id: int | None = None
    first_name: str | None = None
    last_name: str | None = None
    public_name: str | None = None
    avatar: str | None = None

    @pydantic.field_validator("avatar")
    @classmethod
    def resolve_avatar_url(cls, v: typing.Any) -> typing.Any:
        """Automatically prepend MEDIA_BASE_URL if missing."""
        if isinstance(v, str) and v and not v.startswith(("http://", "https://")):
            return f"{consts.MEDIA_BASE_URL}{v.lstrip('/')}"
        return v


class Owner(SourceInfo):
    """Represents the owner of a resource (same fields as SourceInfo)."""

    pass


class SyncInfo(WarnExtraFieldsModel):
    """Synchronization details for a resource."""

    synced_by: dict[str, typing.Any] | None = None
    synced: datetime.datetime | None = None
    source: str | None = None


class Storage(WarnExtraFieldsModel):
    """Represents a storage device on the printer."""

    type: str
    path: str
    mountpoint: str | None = None
    name: str
    read_only: bool = False
    is_sfn: bool | None = None
    file_count: int | None = None
    free_space: int | None = None
    total_space: int | None = None


class PrintFileMeta(WarnExtraFieldsModel):
    """Metadata associated with a print file (statistics parse from G-code)."""

    model_config = pydantic.ConfigDict(extra="allow")

    extruder_colour: str | None = None
    filament_abrasive: bool | None = None
    temperature: int | None = None
    brim_width: int | None = None
    bed_temperature: int | None = None
    ironing: bool | None = None
    nozzle_high_flow: bool | None = None
    support_material: bool | None = None
    filament_type: str | None = None
    filament_cost: float | None = None
    total_height: float | None = None
    max_layer_z: float | None = None
    filament_used_m: float | None = None
    filament_used_mm: float | None = None
    filament_used_g: float | None = None
    filament_used_cm3: float | None = None
    filament_used_mm3: float | None = None
    nozzle_diameter: float | None = None
    fill_density: str | None = None
    printer_model: str | None = None
    estimated_print_time: datetime.timedelta | None = None
    estimated_printing_time_normal_mode: str | None = None
    layer_height: float | None = None
    producer: str | None = None
    slots: list[dict[str, typing.Any]] | None = None
    objects_info: dict[str, typing.Any] | None = None


class FirmwareFileMeta(WarnExtraFieldsModel):
    """Metadata associated with a firmware file."""

    device_type_id: str | None = None
    version: str | None = None
    sem_ver: str | None = None
    build_no: int | None = None
    bbf_version: int | None = None
    printer_model: str | None = None


class BaseFile(WarnExtraFieldsModel):
    """Common fields for all file types."""

    type: str  # Discriminator field
    name: str
    display_name: str | None = None
    size: pydantic.ByteSize | None = None
    hash: str | None = None

    team_id: int | None = None
    upload_id: int | None = None
    uploaded: datetime.datetime | None = None

    path: str | None = None
    display_path: str | None = None
    read_only: bool = False
    m_timestamp: int | None = None

    sync: SyncInfo | None = None
    owner: Owner | None = None

    model_config = pydantic.ConfigDict(extra="allow")


class RegularFile(BaseFile):
    """Represents a generic file."""

    type: typing.Literal["FILE"] = "FILE"  # pyrefly: ignore[bad-override]


class PrintFile(BaseFile):
    """Represents a print file (G-code, BG-code)."""

    type: typing.Literal["PRINT_FILE"] = "PRINT_FILE"  # pyrefly: ignore[bad-override]
    preview_url: str | None = None
    preview_mimetype: str | None = None
    meta: PrintFileMeta | None = None


class FirmwareFile(BaseFile):
    """Represents a firmware file on the printer."""

    type: typing.Literal["FIRMWARE"] = "FIRMWARE"  # pyrefly: ignore[bad-override]
    printer_type: str | None = None
    release_url: pydantic.HttpUrl | None = None
    meta: FirmwareFileMeta | None = None


File = typing.Annotated[PrintFile | FirmwareFile | RegularFile, pydantic.Field(discriminator="type")]


class JobInfo(WarnExtraFieldsModel):
    """Snapshot of a job currently on a printer."""

    id: int | None = None
    origin_id: int | None = None
    path: str | None = None
    state: str | None = None
    progress: float | None = None
    time_printing: int | None = None
    time_remaining: int | None = None
    display_name: str | None = None
    start: datetime.datetime | None = None
    end: datetime.datetime | None = None
    hash: str | None = None
    preview_url: str | None = None
    model_weight: float | None = None
    weight_remaining: float | None = None
    print_height: float | None = None
    total_height: float | None = None
    lifetime_id: str | None = None


class CancelableObject(WarnExtraFieldsModel):
    """Represents an object that can be cancelled during print."""

    id: int
    name: str
    polygon: list[list[float]] | None = None


class JobFailureReason(WarnExtraFieldsModel):
    """Details about a job failure."""

    tag: list[JobFailureTag] = pydantic.Field(default_factory=list)
    other: str | None = None


class Job(WarnExtraFieldsModel):
    """A planned or history job."""

    id: int
    lifetime_id: str | None = None
    printer_uuid: str | None = None
    team_id: int | None = None
    origin_id: int | None = None
    source: str | None = None
    source_info: SourceInfo | None = None

    state: str
    hash: str | None = None
    time_printing: int | None = None
    start: int | None = None
    end: int | None = None
    progress: float | None = None
    planned: dict | None = None

    print_height: float | None = None

    file: File | None = None
    path: str | None = None

    reason: JobFailureReason | None = None

    cancelable_objects: list[CancelableObject] | None = None


class Temperatures(WarnExtraFieldsModel):
    """Printer temperatures."""

    temp_nozzle: float | None = None
    temp_bed: float | None = None
    target_nozzle: float | None = None
    target_bed: float | None = None


class Camera(WarnExtraFieldsModel):
    """Camera information."""

    id: int | None = None  # Numeric ID for snapshots
    token: str | None = None  # Alphanumeric token/id in some contexts?
    name: str | None = None
    origin: str | None = None
    resolution: str | None = None
    snapshot_url: str | None = None

    config: typing.Any | None = None
    options: typing.Any | None = None
    capabilities: typing.Any | None = None
    features: typing.Any | None = None
    sort_order: typing.Any | None = None
    registered: typing.Any | None = None
    team_id: typing.Any | None = None
    printer_uuid: typing.Any | None = None


class TeamUser(WarnExtraFieldsModel):
    """User in a team."""

    id: int
    first_name: str | None = None
    last_name: str | None = None
    public_name: str | None = None
    avatar: str | None = None
    rights_ro: bool | None = None
    rights_rw: bool | None = None
    rights_use: bool | None = None


class Team(WarnExtraFieldsModel):
    """Team information."""

    id: int
    name: str
    role: str | None = None
    description: str | None = None
    capacity: int | None = None
    organization_id: uuid_pkg.UUID | None = None
    prusaconnect_api_key: pydantic.SecretStr | None = None
    user_count: int | None = None
    users: list[TeamUser] | None = None
    invitees: list[typing.Any] | None = None


class NetworkInfo(WarnExtraFieldsModel):
    """Network configuration details."""

    lan_ipv4: str | None = None
    lan_mac: str | None = None
    hostname: str | None = None


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


class UploadStatus(WarnExtraFieldsModel):
    """Status of a file upload to Prusa Connect."""

    id: int
    team_id: int
    name: str
    size: int
    hash: str | None = None
    state: str
    source: str | None = None
