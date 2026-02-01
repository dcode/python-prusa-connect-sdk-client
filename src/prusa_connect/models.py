from enum import StrEnum
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class PrinterState(StrEnum):
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
    def _missing_(cls, value: object) -> Any:
        return cls.UNKNOWN


class SourceInfo(BaseModel):
    id: int | None = None
    first_name: str | None = None
    last_name: str | None = None
    public_name: str | None = None
    avatar: str | None = None


class Owner(SourceInfo):
    pass


class SyncInfo(BaseModel):
    synced_by: dict[str, Any] | None = None
    synced: int | None = None
    source: str | None = None


class FileMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    filament_cost: float | None = None
    total_height: float | None = None
    max_layer_z: float | None = None
    filament_used_m: float | None = None
    filament_used_g: float | None = None
    nozzle_diameter: float | None = None
    fill_density: str | None = None
    printer_model: str | None = None
    estimated_print_time: int | None = None
    layer_height: float | None = None


class File(BaseModel):
    """Represents a file on the printer or Connect cloud."""

    type: str
    name: str
    display_name: str | None = None
    path: str
    read_only: bool = False
    m_timestamp: int | None = None
    size: int | None = None
    hash: str | None = None
    team_id: int | None = None
    meta: FileMeta | None = None
    preview_url: str | None = None


class JobInfo(BaseModel):
    """Snapshot of a job currently on a printer."""

    id: int | None = None
    origin_id: int | None = None
    path: str | None = None
    state: str | None = None
    progress: float | None = None
    time_printing: int | None = None
    time_remaining: int | None = None
    display_name: str | None = None
    start: int | None = None


class Job(BaseModel):
    """A planned or history job."""

    id: int
    lifetime_id: str | None = None
    printer_uuid: str | None = None
    state: str
    hash: str | None = None
    time_printing: int | None = None
    start: int | None = None
    end: int | None = None
    progress: float | None = None
    file: File | None = None
    source_info: SourceInfo | None = None


class Temperatures(BaseModel):
    temp_nozzle: float | None = None
    temp_bed: float | None = None
    target_nozzle: float | None = None
    target_bed: float | None = None


class Camera(BaseModel):
    id: int | None = None  # Numeric ID for snapshots
    token: str | None = None  # Alphanumeric token/id in some contexts?
    name: str | None = None
    origin: str | None = None
    resolution: str | None = None
    snapshot_url: str | None = None


class Team(BaseModel):
    id: int
    name: str
    role: str | None = None


class Printer(BaseModel):
    """Detailed Printer Object.
    Matches structure in `printers.error.response.json` and `printer_details.json`.
    """

    uuid: str | None = None  # UUID might not be in the detail root, but often is
    name: str | None = None
    printer_state: PrinterState | None = Field(
        None, validation_alias=AliasChoices("printer_state", "state")
    )  # API uses 'state' or 'printer_state'
    printer_model: str | None = None
    firmware_version: str | None = Field(None, alias="firmware")
    last_online: float | None = None

    # Nested info
    telemetry: Temperatures | None = Field(None, alias="temp")
    job: JobInfo | None = Field(None, alias="job_info")
    cameras: list[Camera] | None = None

    # Capabilities
    nozzle_diameter: float | None = None
    speed: int | None = None
    flow: int | None = None

    model_config = ConfigDict(extra="ignore")


class PrinterListResponse(BaseModel):
    printers: list[Printer]
