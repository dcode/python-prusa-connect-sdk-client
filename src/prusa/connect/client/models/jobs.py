"""Job models for Prusa Connect SDK."""

import datetime
from enum import StrEnum

import pydantic
from pydantic import AliasChoices, AliasPath

from .cameras import Camera
from .common import SourceInfo, WarnExtraFieldsModel
from .files import File
from .stats import JobStatus


class JobFailureTag(StrEnum):
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


class JobInfo(WarnExtraFieldsModel):
    """Snapshot of a job currently on a printer."""

    id: int | None = None
    origin_id: int | None = None
    path: str | None = None
    state: str | None = None
    progress: float | None = None
    time_printing: datetime.timedelta | None = None
    time_remaining: datetime.timedelta | None = None
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
    canceled: bool = False


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

    state: JobStatus

    cameras: list[Camera] | None = None
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

    cancelable_objects: list[CancelableObject] | None = pydantic.Field(
        None, validation_alias=AliasChoices("cancelable_objects", AliasPath("cancelable", "objects"))
    )
    cancelable_time: datetime.datetime | None = None
