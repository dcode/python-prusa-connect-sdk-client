"""Shared CLI helpers and configuration."""

import logging
import pathlib
import sys
import typing

import better_exceptions
import platformdirs
import structlog
from rich import console as rich_console
from rich import print as rprint

from prusa.connect.client import auth, exceptions, sdk
from prusa.connect.client import consts as sdk_consts
from prusa.connect.client.cli import config

if typing.TYPE_CHECKING:
    from structlog.typing import Processor

# Setup
better_exceptions.hook()
console = rich_console.Console()
logger = structlog.get_logger(sdk_consts.APP_NAME)

_LOGGING_INITIALIZED = False


def configure_logging(verbose: bool | None, debug: bool | None):
    """Sets up structlog/logging based on verbosity."""
    global _LOGGING_INITIALIZED
    global logger

    # If no flags provided and we are already initialized, do nothing (inherit state)
    if verbose is None and debug is None:
        if _LOGGING_INITIALIZED:
            return
        # Fallback defaults if first run
        verbose = False
        debug = False

    _LOGGING_INITIALIZED = True

    if debug:
        level = logging.DEBUG
    elif verbose:
        level = logging.INFO
    else:
        level = logging.WARNING

    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="%H:%M:%S", utc=False),
    ]

    # Cyclopts runs in a terminal, so we usually want pretty logs
    if not sys.stderr.isatty():
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stderr),
    )
    logger = structlog.get_logger(sdk_consts.APP_NAME)


def get_logger():
    """Get the logger for the application."""
    return logger


def get_client(require_auth: bool = True) -> sdk.PrusaConnectClient:
    """Load credentials and return an authenticated client.

    TIP: Credentials are automatically loaded from default
        locations (Env > File). See
        `prusa.connect.client.auth.PrusaConnectCredentials.load_default()`
        for more information.

    Args:
        require_auth: Whether to require authentication.

    Returns:
        An authenticated PrusaConnectClient instance.
    """
    # Attempt to load from default locations (Env > File)
    creds = auth.PrusaConnectCredentials.load_default()

    if creds is not None and not creds.valid:
        try:
            # Attempt to refresh the credentials
            creds.refresh()
        except exceptions.PrusaAuthError:
            logger.info("Failed to refresh credentials.")
            creds = None

    if (creds is None or not creds.valid) and require_auth:
        rprint("[red]Authentication required.[/red]")
        rprint("Please run [bold]prusactl auth login[/bold] to authenticate.")
        sys.exit(1)

    cache_dir = pathlib.Path(platformdirs.user_cache_dir(sdk_consts.APP_NAME, sdk_consts.APP_AUTHOR))

    cache_ttl = config.settings.cache_ttl_hours * 3600
    return sdk.PrusaConnectClient(credentials=creds, cache_dir=cache_dir, cache_ttl=cache_ttl)
