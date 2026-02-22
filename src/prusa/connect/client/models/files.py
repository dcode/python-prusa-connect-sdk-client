"""File models for Prusa Connect SDK."""

import datetime
import typing

import pydantic

from .common import Owner, SyncInfo, WarnExtraFieldsModel


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


class UploadStatus(WarnExtraFieldsModel):
    """Status of a file upload to Prusa Connect."""

    id: int
    team_id: int
    name: str
    size: int
    hash: str | None = None
    state: str
    source: str | None = None
