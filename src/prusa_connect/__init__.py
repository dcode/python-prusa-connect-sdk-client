"""Prusa Connect API Client Library.

A strongly-typed Python client for the Prusa Connect REST API.
"""

from .__version__ import __version__
from .client import PrusaConnectClient
from .exceptions import (
    PrusaApiError,
    PrusaAuthError,
    PrusaConnectError,
    PrusaNetworkError,
)
from .models import (
    Camera,
    File,
    FileMeta,
    Job,
    JobInfo,
    Owner,
    Printer,
    PrinterState,
    SourceInfo,
    SyncInfo,
    Team,
    Temperatures,
)

__all__ = [
    "Camera",
    "File",
    "FileMeta",
    "Job",
    "JobInfo",
    "Owner",
    "Printer",
    "PrinterState",
    "PrusaApiError",
    "PrusaAuthError",
    "PrusaConnectClient",
    "PrusaConnectError",
    "PrusaNetworkError",
    "SourceInfo",
    "SyncInfo",
    "Team",
    "Temperatures",
    "__version__",
]
