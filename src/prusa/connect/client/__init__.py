"""Prusa Connect Client SDK.

This package provides a Python client for interacting with the Prusa Connect API.

How to use the most important parts:
- Explore the submodules to understand the available features. Look closely at
  `auth`, `camera`, `gcode`, `models`, and `sdk`.
- `PrusaConnectClient`: Exposes the core REST interface. Start here for standard monitoring or configuration.
- `PrusaConnectCredentials`: Pass this securely to `PrusaConnectClient` to enable automatic token-refreshing
  and header injection.
"""

import logging

import structlog

# Set default library logging level to WARNING if the user hasn't configured structlog
if not structlog.is_configured():
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING))

from prusa.connect.client.__version__ import __version__
from prusa.connect.client.auth import PrusaConnectCredentials
from prusa.connect.client.camera import PrusaCameraClient
from prusa.connect.client.gcode import GCodeMetadata
from prusa.connect.client.sdk import AuthStrategy, PrusaConnectClient

__all__ = [
    "AuthStrategy",
    "GCodeMetadata",
    "PrusaCameraClient",
    "PrusaConnectClient",
    "PrusaConnectCredentials",
    "__version__",
]
