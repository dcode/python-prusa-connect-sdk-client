"""Pydantic models for Prusa Connect API responses.

This module defines the data structures used by the client to parse
API responses into typed objects.
"""

from .cameras import (
    Camera,
    CameraConfig,
    CameraNetworkInfo,
    CameraOptions,
    CameraResolution,
)
from .common import (
    NetworkInfo,
    Owner,
    SourceInfo,
    SyncInfo,
    WarnExtraFieldsModel,
)
from .config import AppConfig, AuthConfig
from .files import (
    BaseFile,
    File,
    FirmwareFile,
    FirmwareFileMeta,
    PrintFile,
    PrintFileMeta,
    RegularFile,
    Storage,
    UploadStatus,
)
from .jobs import (
    CancelableObject,
    Job,
    JobFailureReason,
    JobFailureTag,
    JobInfo,
    JobStatus,
)
from .printers import (
    FirmwareSupport,
    Printer,
    PrinterCommand,
    PrinterListResponse,
    PrinterState,
    SlotInfo,
    Temperatures,
    Tool,
)
from .stats import (
    JobsSuccess,
    JobsSuccessSeries,
    MaterialQuantity,
    PlannedTasks,
    PlannedTasksSeries,
    PrintingNotPrinting,
    PrintingNotPrintingEntry,
    StatsModel,
)
from .teams import Team, TeamUser

# ruff: noqa: RUF022
__all__ = [
    # Cameras
    "Camera",
    "CameraConfig",
    "CameraNetworkInfo",
    "CameraOptions",
    "CameraResolution",
    # Common
    "NetworkInfo",
    "Owner",
    "SourceInfo",
    "SyncInfo",
    "WarnExtraFieldsModel",
    # Files
    "BaseFile",
    "File",
    "FirmwareFile",
    "FirmwareFileMeta",
    "PrintFile",
    "PrintFileMeta",
    "RegularFile",
    "Storage",
    "UploadStatus",
    # Jobs
    "CancelableObject",
    "Job",
    "JobFailureReason",
    "JobFailureTag",
    "JobInfo",
    "JobStatus",
    # Printers
    "FirmwareSupport",
    "Printer",
    "PrinterCommand",
    "PrinterListResponse",
    "PrinterState",
    "SlotInfo",
    "Temperatures",
    "Tool",
    # Stats
    "JobsSuccess",
    "JobsSuccessSeries",
    "MaterialQuantity",
    "PlannedTasks",
    "PlannedTasksSeries",
    "PrintingNotPrinting",
    "PrintingNotPrintingEntry",
    "StatsModel",
    # Teams
    "Team",
    "TeamUser",
    # Config
    "AppConfig",
    "AuthConfig",
]
