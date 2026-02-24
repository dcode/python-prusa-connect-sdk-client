"""Shared CLI helpers and configuration."""

import collections.abc
import json as _json
import logging
import pathlib
import sys
import typing

import better_exceptions
import platformdirs
import structlog
from rich import console as rich_console
from rich.text import Text

from prusa.connect.client import auth, exceptions, sdk
from prusa.connect.client import consts as sdk_consts
from prusa.connect.client.cli import config

if typing.TYPE_CHECKING:
    from structlog.typing import Processor

# Setup
better_exceptions.hook()
console = rich_console.Console()
err_console = rich_console.Console(stderr=True)
logger = structlog.get_logger(sdk_consts.APP_NAME)

# -- Output format ----------------------------------------------------------

_output_format: config.OutputFormat | None = None  # None means "resolve lazily from config/TTY"


def set_output_format(fmt: str | None) -> None:
    """Set the output format (called from --format CLI flag).

    Calls `sys.exit` if an invalid format is specified.
    """
    global _output_format
    try:
        _output_format = config.OutputFormat(fmt) if fmt is not None else None
    except ValueError:
        output_message(
            (
                f"[bold][red]Error[/red][/bold]: `{fmt}` is not a valid output "
                f"format. Valid formats are: {', '.join(config.OutputFormat.__members__.values())}"
            ),
            error=True,
        )
        sys.exit(1)


def get_output_format() -> config.OutputFormat:
    """Resolve the active output format: CLI flag > config > TTY auto-detect."""
    if _output_format is not None:
        return _output_format
    cfg_fmt = getattr(config.settings, "output_format", None)
    if cfg_fmt:
        return cfg_fmt
    return config.OutputFormat.RICH if sys.stdout.isatty() else config.OutputFormat.PLAIN


def _strip_markup(text: str) -> str:
    """Remove Rich markup tags from a string."""
    return Text.from_markup(str(text)).plain


def output_message(msg: str, *, error: bool = False) -> None:
    """Print a status/error message respecting the current output format.

    - rich: renders markup with color to stdout (or stderr for errors)
    - plain: strips markup, writes to stdout (errors to stderr)
    - json: strips markup, always writes to stderr (stdout reserved for JSON)
    """
    fmt = get_output_format()
    if fmt in ("plain", "json"):
        plain = _strip_markup(msg)
        to_stderr = error or fmt == "json"
        print(plain, file=sys.stderr if to_stderr else sys.stdout)
    else:
        target = err_console if error else console
        target.print(msg)


def output_table(
    title: str,
    columns: list[str],
    rows: list[list[str]],
    *,
    column_styles: collections.abc.Sequence[str | None] | None = None,
    sections_before: set[int] | None = None,
) -> None:
    """Print tabular data respecting the current output format.

    Args:
        title: Table title (used as rich title; as ``# title`` comment in plain).
        columns: Column header names.
        rows: Row data as lists of strings (may contain Rich markup; stripped in
            plain/json modes).
        column_styles: Optional per-column Rich style names (ignored in plain/json).
        sections_before: Set of row indices before which ``table.add_section()``
            is called (rich only; ignored in plain/json).
    """
    from rich.table import Table as _RichTable

    fmt = get_output_format()

    if fmt == "json":
        keys = [c.lower().replace(" ", "_").replace("(", "").replace(")", "").strip("_") for c in columns]
        data = [dict(zip(keys, [_strip_markup(c) for c in row], strict=False)) for row in rows]
        print(_json.dumps(data))
    elif fmt == "plain":
        print(f"# {title}")
        print("\t".join(columns))
        for row in rows:
            print("\t".join(_strip_markup(c) for c in row))
    else:
        table = _RichTable(title=title)
        styles = column_styles or []
        for i, col in enumerate(columns):
            style = styles[i] if i < len(styles) else None
            table.add_column(col, style=style)
        for i, row in enumerate(rows):
            if sections_before and i in sections_before:
                table.add_section()
            table.add_row(*[str(c) for c in row])
        console.print(table)


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
        output_message("Authentication required.", error=True)
        output_message("Please run 'prusactl auth login' to authenticate.", error=True)
        sys.exit(1)

    cache_dir = pathlib.Path(platformdirs.user_cache_dir(sdk_consts.APP_NAME, sdk_consts.APP_AUTHOR))

    cache_ttl = config.settings.cache_ttl_hours * 3600
    return sdk.PrusaConnectClient(credentials=creds, cache_dir=cache_dir, cache_ttl=cache_ttl)
