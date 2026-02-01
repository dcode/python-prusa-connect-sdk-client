"""CLI entry point for Prusa Connect."""

import fnmatch
import getpass
import json
import logging
import os
import sys
from pathlib import Path
from typing import Annotated, Literal

import better_exceptions
import cyclopts
import structlog
from rich import print as rprint
from rich.console import Console
from rich.table import Table
from structlog.typing import Processor

from prusa_connect.__version__ import __version__
from prusa_connect.auth import PrusaConnectCredentials, interactive_login
from prusa_connect.client import PrusaConnectClient
from prusa_connect.config import settings
from prusa_connect.exceptions import PrusaAuthError, PrusaConnectError

# Setup
better_exceptions.hook()
console = Console()
logger = structlog.get_logger()

# Define the App
app = cyclopts.App(
    name="prusactl",
    help="Prusa Connect CLI and API Client",
    version=__version__,
    version_flags=["--version"],
    help_flags=["--help"],
)


# --- HELPERS ---
def configure_logging(verbose: bool):
    """Sets up structlog/logging based on verbosity."""
    level = logging.DEBUG if verbose else logging.WARNING

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


def get_client() -> PrusaConnectClient:
    """Load credentials and return an authenticated client."""
    creds = PrusaConnectCredentials.from_file(settings.tokens_file)

    if creds is not None and not creds.valid:
        try:
            # Attempt to refresh the credentials
            creds.refresh()
        except PrusaAuthError:
            logger.info("Failed to refresh credentials. Re-authenticating...")
            # If refresh fails, clear the credentials
            creds = None

    if creds is None or not creds.valid:
        rprint("[yellow]Authentication required.[/yellow]")

        email = settings.prusa_email or os.environ.get("PRUSA_EMAIL")
        if not email:
            print("Email: ", end="", flush=True)
            email = input().strip()

        password = settings.prusa_password or os.environ.get("PRUSA_PASSWORD")
        if not password:
            password = getpass.getpass("Password: ")

        def otp_callback() -> str:
            print("Enter 2FA/TOTP Code: ", end="", flush=True)
            return input().strip()

        try:
            token_data = interactive_login(email, password, otp_callback=otp_callback)

            def save_tokens(data):
                with open(settings.tokens_file, "w") as f:
                    json.dump(data, f, indent=2)

            save_tokens(token_data)
            creds = PrusaConnectCredentials(token_data, token_saver=save_tokens)
            rprint("[green]Authentication successful![/green]")

        except Exception as e:
            rprint(f"[bold red]Authentication failed: {e}[/bold red]")
            sys.exit(1)

    return PrusaConnectClient(credentials=creds)


# --- COMMANDS ---


@app.command(name="list-printers")
def list_printers(
    filter: Annotated[str, cyclopts.Parameter(name="filter", help="Glob pattern to filter names")] = "*",
    verbose: Annotated[bool, cyclopts.Parameter(name=["--verbose", "-v"])] = False,
):
    """List all printers associated with the account."""
    configure_logging(verbose)
    client = get_client()
    printers = client.get_printers()

    table = Table(title="Printers")
    table.add_column("Name", style="cyan")
    table.add_column("UUID", style="magenta")
    table.add_column("State", style="green")
    table.add_column("Model", style="blue")

    # Filter
    filtered = [p for p in printers if fnmatch.fnmatch(p.name or "", filter)]

    for p in filtered:
        logger.debug("Printer", json=p.model_dump_json())
        state_str = str(p.printer_state) if p.printer_state else "UNKNOWN"
        table.add_row(
            p.name or "Unknown",
            p.uuid or "Unknown",
            state_str,
            p.printer_model or "N/A",
        )
    console.print(table)


@app.default
def default_action(
    filter: Annotated[str, cyclopts.Parameter(name="filter", help="Glob pattern to filter names")] = "*",
    verbose: Annotated[bool, cyclopts.Parameter(name=["--verbose", "-v"])] = False,
):
    """Default action (alias for list-printers)."""
    list_printers(filter=filter, verbose=verbose)


@app.command(name="show")
def show(
    printer_id: Annotated[str, cyclopts.Parameter(help="Printer UUID")],
    verbose: Annotated[bool, cyclopts.Parameter(name=["--verbose", "-v"])] = False,
):
    """Show detailed status for a specific printer."""
    configure_logging(verbose)
    client = get_client()

    try:
        p = client.get_printer(printer_id)

        table = Table(title=f"Printer: {p.name}", show_header=False)
        table.add_row("UUID", p.uuid)
        table.add_row("State", str(p.printer_state))
        table.add_row("Model", p.printer_model)

        if p.telemetry:
            table.add_row("Nozzle", f"{p.telemetry.temp_nozzle}°C")
            table.add_row("Bed", f"{p.telemetry.temp_bed}°C")

        if p.job:
            table.add_row("Job", p.job.display_name or "Unknown")
            table.add_row("Progress", f"{p.job.progress}%")
            if p.job.time_remaining:
                table.add_row("Time Left", f"{p.job.time_remaining}s")

        console.print(table)
    except PrusaConnectError as e:
        rprint(f"[red]Error:[/red] {e}")


@app.command(name="list-cameras")
def list_cameras(
    verbose: Annotated[bool, cyclopts.Parameter(name=["--verbose", "-v"])] = False,
):
    """List all cameras."""
    configure_logging(verbose)
    client = get_client()
    cameras = client.get_cameras()

    table = Table(title="Cameras")
    table.add_column("Name", style="cyan")
    table.add_column("ID (Numeric)", style="magenta")
    table.add_column("Token", style="green")
    table.add_column("Origin", style="blue")

    for c in cameras:
        table.add_row(
            c.name or "Unknown",
            str(c.id) if c.id else "N/A",
            c.token or "N/A",
            c.origin or "N/A",
        )
    console.print(table)


@app.command(name="list-jobs")
def list_jobs(
    team: Annotated[int | None, cyclopts.Parameter(name="--team", help="Filter by Team ID")] = None,
    printer: Annotated[str | None, cyclopts.Parameter(name="--printer", help="Filter by Printer UUID")] = None,
    verbose: Annotated[bool, cyclopts.Parameter(name=["--verbose", "-v"])] = False,
):
    """List jobs. If no filters provided, lists jobs for all user's teams."""
    configure_logging(verbose)
    client = get_client()

    all_jobs = []

    if printer:
        # Get jobs for specific printer
        all_jobs.extend(client.get_printer_jobs(printer))
    elif team:
        # Get jobs for specific team
        all_jobs.extend(client.get_team_jobs(team))
    else:
        # Get jobs for all teams
        teams = client.get_teams()
        for t in teams:
            all_jobs.extend(client.get_team_jobs(t.id))

    table = Table(title="Jobs")
    table.add_column("ID", style="cyan")
    table.add_column("Printer", style="magenta")
    table.add_column("State", style="green")
    table.add_column("Name", style="blue")
    table.add_column("Progress", style="yellow")

    for j in all_jobs:
        table.add_row(
            str(j.id),
            j.printer_uuid or "Unknown",
            j.state or "Unknown",
            j.file.name if j.file else "Unknown",
            f"{j.progress}%" if j.progress is not None else "N/A",
        )

    console.print(table)


# Printer Command Group
@app.command(name="printer")
def printer_cmd(
    command: Annotated[Literal["pause", "resume", "stop", "show"], cyclopts.Parameter(help="Command to send")],
    printer_ids: Annotated[list[str], cyclopts.Parameter(help="Printer UUIDs")],
    verbose: Annotated[bool, cyclopts.Parameter(name=["--verbose", "-v"])] = False,
):
    """Send commands to one or more printers."""
    configure_logging(verbose)
    client = get_client()

    # Map friendly names to API commands
    # 'show' is special handled
    cmd_map = {"pause": "PAUSE_PRINT", "resume": "RESUME_PRINT", "stop": "STOP_PRINT"}

    for pid in printer_ids:
        if command == "show":
            # Reuse show logic provided separately, but here we iterate
            # Ideally we call the show function but it expects single arg.
            # We can just copy logic or call it if refactored.
            # For simplicity, calling the client directly here akin to show command.
            try:
                p = client.get_printer(pid)
                rprint(f"[bold]Printer: {p.name} ({pid})[/bold]")
                rprint(f"  State: {p.printer_state}")
                if p.telemetry:
                    rprint(f"  Temp: {p.telemetry.temp_nozzle}°C / {p.telemetry.temp_bed}°C")
                if p.job:
                    rprint(f"  Job: {p.job.display_name} ({p.job.progress}%)")
                rprint("")
            except Exception as e:
                rprint(f"[red]Error fetching {pid}: {e}[/red]")
            continue

        api_cmd = cmd_map.get(command)
        if not api_cmd:
            rprint(f"[red]Unknown command {command}[/red]")
            continue

        try:
            if client.send_command(pid, api_cmd):
                rprint(f"[green]Sent {api_cmd} to {pid}[/green]")
        except Exception as e:
            rprint(f"[red]Failed to send {api_cmd} to {pid}: {e}[/red]")


# Camera Command Group
@app.command(name="camera")
def camera_cmd(
    command: Annotated[Literal["snapshot", "trigger"], cyclopts.Parameter(help="Action")],
    camera_id: Annotated[str, cyclopts.Parameter(help="Camera ID (Numeric) or Token")],
    output: Annotated[Path | None, cyclopts.Parameter(help="Output file path for snapshot")] = None,
    verbose: Annotated[bool, cyclopts.Parameter(name=["--verbose", "-v"])] = False,
):
    """Camera actions."""
    configure_logging(verbose)
    client = get_client()

    # Resolve ID/Token
    # We look up the camera to get both ID and Token effectively
    cameras = client.get_cameras()
    match = next((c for c in cameras if str(c.id) == camera_id or c.token == camera_id), None)

    real_id = camera_id
    real_token = camera_id

    if match:
        if match.id:
            real_id = str(match.id)
        if match.token:
            real_token = match.token
        logger.debug("Resolved camera", name=match.name, id=real_id, token=real_token)
    else:
        logger.warning("Camera not found in list, using input value as-is.")

    if command == "snapshot":
        try:
            # Snapshot needs Numeric ID
            data = client.get_snapshot(real_id)
            if output:
                if str(output) == "-":
                    sys.stdout.buffer.write(data)
                else:
                    output.write_bytes(data)
                    rprint(f"[green]Saved snapshot to {output}[/green]")
            else:
                rprint(f"[green]Snapshot received: {len(data)} bytes[/green]")
        except Exception as e:
            if str(output) == "-":
                # If piping, print error to stderr
                sys.stderr.write(f"Failed to get snapshot: {e}\n")
            else:
                rprint(f"[red]Failed to get snapshot: {e}[/red]")

    elif command == "trigger":
        try:
            # Trigger needs Token
            if client.trigger_snapshot(real_token):
                rprint(f"[green]Triggered snapshot for {camera_id} (Token: {real_token})[/green]")
        except Exception as e:
            rprint(f"[red]Failed to trigger snapshot: {e}[/red]")


@app.command(name="api")
def api(
    path: Annotated[str, cyclopts.Parameter(help="API endpoint (e.g. /printers)")],
    method: Annotated[str, cyclopts.Parameter(help="HTTP Method")] = "GET",
    data: Annotated[str | None, cyclopts.Parameter(help="JSON data body")] = None,
    output: Annotated[Path | None, cyclopts.Parameter(help="Output file for response")] = None,
    verbose: Annotated[bool, cyclopts.Parameter(name=["--verbose", "-v"])] = False,
):
    """Make a raw authenticated API request."""
    configure_logging(verbose)
    client = get_client()

    kwargs = {}
    if data:
        kwargs["json"] = json.loads(data)

    # Use raw=True if output is specified to handle binary
    raw_mode = output is not None

    # Check if we should default to raw for binary-like paths if not specified?
    # For now, explicit output flag implies raw.

    try:
        res = client._request(method, path, raw=raw_mode, **kwargs)

        if output:
            if str(output) == "-":
                if hasattr(res, "content"):
                    sys.stdout.buffer.write(res.content)
                else:
                    print(json.dumps(res, indent=2))
            else:
                if hasattr(res, "content"):
                    output.write_bytes(res.content)
                else:
                    # If for some reason it's not a response object (unlikely with raw=True), dump json
                    with open(output, "w") as f:
                        json.dump(res, f, indent=2)
                rprint(f"[green]Response saved to {output}[/green]")
        else:
            rprint(res)
    except Exception as e:
        if output and str(output) == "-":
             sys.stderr.write(f"API Request Failed: {e}\n")
        else:
            rprint(f"[red]API Request Failed: {e}[/red]")


def main():
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
