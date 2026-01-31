import json
import fnmatch
import structlog
import logging
import sys
import os
import getpass
from datetime import datetime
from typing import Optional, Literal, Annotated, Any
from rich.console import Console
from rich.table import Table
from rich import print as rprint
from pydantic import Field, BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict, CliSubCommand, CliPositionalArg, CliApp, CliImplicitFlag

from .config import settings
from .auth import load_tokens, save_tokens, refresh_access_token, login_and_get_token, is_token_expired
from .api import PrusaConnectAPI
import better_exceptions

better_exceptions.hook()
console = Console()
logger = structlog.get_logger()

class ListPrinters(BaseModel):
    # TODO(dcode): This should be a positional arg
    # TODO(dcode): Add glob support 
    printer_id: CliPositionalArg[Optional[str]] = Field(None, description="Printer UUID or Name (supports shell-style globs)")

    def cli_cmd(self):
        return list_printers(self.printer_id)

class ListCameras(BaseModel):
    """List cameras for a printer or all printers if no printer is specified."""
    # TODO(dcode): This should be a positional arg
    camera_id: Annotated[str | None, Field(description="Camera ID", validate_default=True)] = None
    printer_id: Annotated[str | None, Field(description="Printer UUID or Name (supports shell-style globs)", validate_default=True)] = None

    def cli_cmd(self):
        return list_cameras(self.camera_id, self.printer_id)


class Show(BaseModel):
    printer_id: CliPositionalArg[str] = Field(None, description="Printer UUID or Name")
    
    def cli_cmd(self):
        return show_printer(self.printer_id)

def do_api_request(path: str, method: str = "GET", data: Optional[str] = None):
    token = get_valid_token()
    api = PrusaConnectAPI(token)
    
    if path.startswith("http"):
        url = path
    else:
        if path.startswith("/"):
            url = f"https://connect.prusa3d.com{path}"
        else:
            url = f"https://connect.prusa3d.com/{path}"

    logger.debug(f"Request: {method} {url}")
    
    json_data = None
    if data:
        try:
            json_data = json.loads(data)
        except json.JSONDecodeError:
            pass 
    
    try:
        if json_data:
            resp = api.session.request(method, url, json=json_data)
        else:
            resp = api.session.request(method, url, data=data)
            
        if logging.getLogger().getEffectiveLevel() <= logging.INFO:
            rprint(f"[bold]HTTP/{resp.status_code} {resp.reason}[/bold]", file=sys.stderr)
            for k, v in resp.headers.items():
                rprint(f"[cyan]{k}[/cyan]: {v}", file=sys.stderr)
            rprint("", file=sys.stderr)

        try:
            rprint(resp.json())
        except ValueError:
            print(resp.text)
            
    except Exception as e:
        logging.exception("Request failed", exception=e)
        sys.exit(1)

class ApiCmd(BaseModel):
    path: CliPositionalArg[str] = Field(..., description="API endpoint path (e.g. /app/config or full URL)")
    method: str = Field("GET", description="HTTP method (GET, POST, PUT, DELETE, etc.)")
    data: Optional[str] = Field(None, description="Request body data (JSON string)")
    
    def cli_cmd(self):
        do_api_request(self.path, self.method, self.data)

class PrinterControl(BaseModel):
    printer_id: CliPositionalArg[str] = Field(..., description="Printer UUID or Name")
    command: CliPositionalArg[str] = Field(..., description="Command (pause, resume, stop, cancel)")

    def cli_cmd(self):
        control_printer(self.printer_id, self.command)

class CameraSnapshot(BaseModel):
    camera_id: CliPositionalArg[str] = Field(..., description="Camera ID or Name")
    output: Annotated[Optional[str], Field(alias="output", description="Output file path")] = None
    trigger: Annotated[bool, Field(alias="trigger", description="Trigger new snapshot only")] = False

    def cli_cmd(self):
        handle_camera_snapshot(self.camera_id, self.output, self.trigger)

class Move(BaseModel):
    printer_id: CliPositionalArg[str] = Field(..., description="Printer UUID or Name")
    x: Annotated[Optional[float], Field(description="Target X position")] = None
    y: Annotated[Optional[float], Field(description="Target Y position")] = None
    z: Annotated[Optional[float], Field(description="Target Z position")] = None
    e: Annotated[Optional[float], Field(description="Target E position")] = None
    feedrate: int = Field(3000, description="Feedrate in mm/min")

    def cli_cmd(self):
        move_printer(self.printer_id, self.x, self.y, self.z, self.e, self.feedrate)

class Files(BaseModel):
    printer_id: CliPositionalArg[str] = Field(..., description="Printer UUID or Name")
    
    def cli_cmd(self):
        list_files(self.printer_id)

class Telemetry(BaseModel):
    printer_id: CliPositionalArg[str] = Field(..., description="Printer UUID or Name")
    granularity: int = Field(15, description="Data granularity in seconds")
    
    def cli_cmd(self):
        get_telemetry_cli(self.printer_id, self.granularity)

class Jobs(BaseModel):
    printer_id: CliPositionalArg[str] = Field(..., description="Printer UUID or Name")
    limit: int = Field(10, description="Number of jobs to show")
    
    def cli_cmd(self):
        list_jobs(self.printer_id, self.limit)

class Queue(BaseModel):
    printer_id: CliPositionalArg[str] = Field(..., description="Printer UUID or Name")
    
    def cli_cmd(self):
        list_queue(self.printer_id)

class Root(BaseSettings, cli_parse_args=True, cli_exit_on_error=False):
    list_printers: Annotated[CliSubCommand[ListPrinters], Field(alias="list-printers", description="List printers")]
    list_cameras: Annotated[CliSubCommand[ListCameras], Field(alias="list-cameras", description="List cameras")]
    show: Annotated[CliSubCommand[Show], Field(alias="show", description="Show printer details")]
    api: Annotated[CliSubCommand[ApiCmd], Field(alias="api", description="Make raw API request (like httpie)")]
    control: Annotated[CliSubCommand[PrinterControl], Field(alias="control", description="Control printer (pause, resume, stop)")]
    snapshot: Annotated[CliSubCommand[CameraSnapshot], Field(alias="snapshot", description="Get or trigger camera snapshot")]
    move: Annotated[CliSubCommand[Move], Field(alias="move", description="Move printer axes")]
    files: Annotated[CliSubCommand[Files], Field(alias="files", description="List files on printer")]
    telemetry: Annotated[CliSubCommand[Telemetry], Field(alias="telemetry", description="Get printer telemetry")]
    jobs: Annotated[CliSubCommand[Jobs], Field(alias="jobs", description="List job history")]
    queue: Annotated[CliSubCommand[Queue], Field(alias="queue", description="List print queue")]
    verbose: CliImplicitFlag[bool] = Field(False, description="Enable verbose logging (INFO level)")
    debug: CliImplicitFlag[bool] = Field(False, description="Enable debug logging (DEBUG level)")
    
    def cli_cmd(self):
        configure_logging(self.verbose, self.debug)
        CliApp.run_subcommand(self)

def configure_logging(verbose: bool, debug: bool):
    if debug:
        min_level = logging.DEBUG
    elif verbose:
        min_level = logging.INFO
    else:
        min_level = logging.WARNING
    
    logging.basicConfig(level=min_level)
    # Also update root logger level if basicConfig was already called (it does nothing if already configured)
    logging.getLogger().setLevel(min_level)

    
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
    ]

    if sys.stderr.isatty():
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        processors.append(structlog.processors.JSONRenderer())
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(min_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stderr),
        cache_logger_on_first_use=False
    )

def get_valid_token() -> str:
    token_data = load_tokens(str(settings.tokens_file))
    
    if token_data:
        if is_token_expired(token_data):
            logger.info("Access token expired. Refreshing...")
            refresh_token_str = token_data.get('refresh_token')
            if refresh_token_str:
                new_tokens = refresh_access_token(refresh_token_str)
                if new_tokens:
                    token_data.update(new_tokens)
                    save_tokens(token_data, str(settings.tokens_file))
                else:
                    logger.warning("Refresh failed. Re-authentication required.")
                    token_data = None
            else:
                logger.warning("No refresh token found. Re-authentication required.")
                token_data = None
        else:
            logger.debug("Access token is valid")

    if not token_data:
        rprint("[yellow]Authentication required.[/yellow]")
        email = settings.prusa_email or os.environ.get("PRUSA_EMAIL")
        password = settings.prusa_password or os.environ.get("PRUSA_PASSWORD")
        
        if not email or not password:
            print("Email: ", end="", flush=True)
            email = input().strip()
            password = getpass.getpass("Password: ")
        
        token_data = login_and_get_token(email, password)
        if token_data:
            save_tokens(token_data, str(settings.tokens_file))
            rprint("[green]Authentication successful![/green]")
        else:
            rprint("[bold red]Authentication failed.[/bold red]")
            sys.exit(1)
            
    return token_data.get('access_token')

def list_printers(printer_id: str | None = None):
    # TODO(dcode): Implement glob filtering
    token = get_valid_token()
    api = PrusaConnectAPI(token)
    printers = api.get_printers()
    pattern = printer_id or "*"
    
    table = Table(title="Printers")
    table.add_column("Name", style="cyan")
    table.add_column("UUID", style="magenta")
    table.add_column("State", style="green")
    table.add_column("Printer Model", style="blue")
    table.add_column("Firmware", style="yellow")
    table.add_column("Last Online", style="orange1")
    
    filtered_printers = [
        p for p in printers if fnmatch.fnmatch(p.get('name'), pattern)
    ]
    for p in filtered_printers:
        table.add_row(
            p.get('name', 'Unknown'),
            p.get('uuid', 'Unknown'),
            p.get('printer_state', 'Unknown'),
            p.get('printer_model', 'Unknown'),
            p.get('firmware', 'Unknown'),
            datetime.fromtimestamp(p.get('last_online', 0)).strftime("%Y-%m-%d %H:%M:%S")
        )
    
    console.print(table)

def list_cameras(camera_id: str | None = None, printer_id: str | None = None):
    # TODO(dcode): Implement glob filtering
    # TODO(dcode): Implement printer_id filtering
    token = get_valid_token()
    api = PrusaConnectAPI(token)
    cameras = api.get_global_cameras()
    
    table = Table(title="Cameras")
    table.add_column("Name", style="cyan")
    table.add_column("ID", style="magenta")
    table.add_column("Printer UUID", style="blue")
    
    for c in cameras:
        table.add_row(
            c.get('name', 'Unknown'),
            str(c.get('id', 'Unknown')),
            c.get('printer_uuid', 'N/A')
        )
            
    console.print(table)

def show_printer(printer_id: Optional[str]):
    token = get_valid_token()
    api = PrusaConnectAPI(token)
    
    if printer_id:
        details = api.get_printer_details(printer_id)
        if details:
             print_printer_details(details)
        else:
            printers = api.get_printers()
            found = [p for p in printers if p.get('name') == printer_id]
            if found:
                details = api.get_printer_details(found[0]['uuid'])
                print_printer_details(details)
            else:
                rprint(f"[red]Printer {printer_id} not found.[/red]")
    else:
        printers = api.get_printers()
        table = Table(title="Printer Status")
        table.add_column("Name", style="cyan")
        table.add_column("UUID", style="magenta")
        table.add_column("Status", style="green")
        table.add_column("Time Remaining", style="yellow")
        
        for p in printers:
            uuid = p.get('uuid')
            time_rem = ""
            job = p.get('job')
            if job and 'time_remaining' in job:
                 tr = job['time_remaining']
                 if tr != -1:
                     time_rem = str(tr)
            
            table.add_row(
                p.get('name', 'Unknown'),
                uuid,
                p.get('status', 'Unknown'),
                time_rem
            )
        console.print(table)

def print_printer_details(details: dict):
    logger.debug("Printer details", details=json.dumps(details, ensure_ascii=True, check_circular=True) if isinstance(details, dict) else details)

    table = Table(title=f"Printer: {details.get('name', 'Unknown')}", show_header=False)

    flat_details = flatten_dict(details)
    for k, v in flat_details.items():
        table.add_row(k, str(v))
    
    console.print(table)
    
    if 'cameras' in details:
        rprint("\n[bold]Cameras embedded in details:[/bold]")
        for c in details['cameras']:
             rprint(f"- {c.get('name')} (ID: {c.get('id')})")

def flatten_dict(d: dict[str, Any], levels: int = 3) -> dict[str, str]:
    """
    Flatten a nested dictionary to a single level.

    Values must be renderable to a string using str().

    Args:
        d (dict[str, Any]): The dictionary to flatten.
        levels (int): The number of levels to flatten.
    
    Returns:
        dict[str, str]: The flattened dictionary.
    """
    if levels <= 0:
        return d
    if not isinstance(d, dict):
        return d

    flattened = {}
    for k, v in d.items():
        if isinstance(v, dict):
            flatter = flatten_dict(v, levels - 1)
            for k2, v2 in flatter.items():
                flattened[f"{k}.{k2}"] = v2
        elif isinstance(v, list):
            if len(v) > 0:
                if isinstance(v[0], dict):
                    flatter = flatten_dict(v, levels - 1)
                    for k2, v2 in flatter.items():
                        flattened[f"{k}.{k2}"] = v2
                else:
                    flattened[k] = ', '.join(v)
        else:
            flattened[k] = str(v)
    
    return flattened

def control_printer(printer_id: str, command: str):
    token = get_valid_token()
    api = PrusaConnectAPI(token)
    
    uuid = resolve_printer_uuid(api, printer_id)
        
    # Map friendly names to likely API commands
    # based on "MOVE_Z" example, it seems commands are UPPERCASE_WITH_UNDERSCORES
    # "pause" -> "PAUSE_PRINT" ? "paused" state is "PAUSED".
    # "stop" -> "STOP_PRINT" ?
    # "cancel" -> "CANCEL_JOB" ?
    # "resume" -> "RESUME_PRINT" ?
    # Without definitive list, straightforward UPPERCASE might be safest for generic commands, 
    # but "pause" might be "PAUSE_PRINT". 
    # Let's try to map them based on common Prusa/OctoPrint conventions if possible, 
    # OR just trust the user input if it's already uppercase.
    # Actually, let's just uppercase them for now to be safe against "pause" vs "PAUSE".
    # User can pass "PAUSE_PRINT" if needed.
    # WAIT, if I just uppercase "pause" -> "PAUSE". It might expect "PAUSE_PRINT".
    # Let's add a mapping for the known CLI verbs.
    
    command_map = {
        "pause": "PAUSE_PRINT",
        "resume": "RESUME_PRINT",
        "stop": "STOP_PRINT",
        "cancel": "CANCEL_JOB",
    }
    
    api_command = command_map.get(command.lower(), command.upper())
        
    valid_commands = ["pause", "resume", "stop", "cancel"]
    if command.lower() not in valid_commands and command != api_command:
         # If it's a custom command, we just warn if it looks weird, but allow it.
         pass
        
    if api.send_printer_command(uuid, api_command):
        rprint(f"[green]Command '{api_command}' sent successfully to {printer_id}.[/green]")
    else:
        rprint(f"[red]Failed to send command '{api_command}'.[/red]")
        sys.exit(1)

def handle_camera_snapshot(camera_id: str, output: Optional[str], trigger: bool):
    token = get_valid_token()
    api = PrusaConnectAPI(token)
    
    if trigger:
        if api.take_camera_snapshot(camera_id):
            rprint(f"[green]Snapshot triggered for camera {camera_id}.[/green]")
        else:
            rprint(f"[red]Failed to trigger snapshot.[/red]")
            sys.exit(1)
    else:
        content = api.get_latest_snapshot(camera_id)
        if content:
            if output:
                with open(output, "wb") as f:
                    f.write(content)
                rprint(f"[green]Snapshot saved to {output}[/green]")
            else:
                rprint(f"[green]Snapshot retrieved ({len(content)} bytes). Use --output to save.[/green]")
        else:
            rprint(f"[red]Failed to retrieve snapshot.[/red]")
            sys.exit(1)

def resolve_printer_uuid(api: PrusaConnectAPI, printer_id: str) -> str:
    """Helper to resolve printer name or UUID to a valid UUID."""
    if len(printer_id) < 32:
        printers = api.get_printers()
        found = [p for p in printers if p.get('name') == printer_id]
        if found:
            return found[0]['uuid']
        else:
            # Try partial match or glob? For now strict name match or UUID.
            rprint(f"[red]Printer {printer_id} not found.[/red]")
            sys.exit(1)
    return printer_id

def move_printer(printer_id: str, x: Optional[float], y: Optional[float], z: Optional[float], e: Optional[float], feedrate: int):
    token = get_valid_token()
    api = PrusaConnectAPI(token)
    uuid = resolve_printer_uuid(api, printer_id)
    
    axis_data = {"feedrate": feedrate}
    if x is not None: axis_data["x"] = x
    if y is not None: axis_data["y"] = y
    if z is not None: axis_data["z"] = z
    if e is not None: axis_data["e"] = e
    
    if len(axis_data) == 1: # Only feedrate
        rprint("[yellow]No axes specified to move.[/yellow]")
        return

    if api.move_axis(uuid, axis_data):
        rprint(f"[green]Move command sent to {printer_id}.[/green]")
    else:
        rprint(f"[red]Failed to move printer.[/red]")
        sys.exit(1)

def list_files(printer_id: str):
    token = get_valid_token()
    api = PrusaConnectAPI(token)
    uuid = resolve_printer_uuid(api, printer_id)
    
    data = api.get_files(uuid)
    files = data.get("files", [])
    
    table = Table(title=f"Files on {printer_id}")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Size", style="green")
    table.add_column("Timestamp", style="blue")
    
    for f in files:
        # Assuming file structure based on common API patterns, need to verify with response json
        # files_response.json is massive, likely has children.
        # "children" might be the key if it's a tree.
        # Just dumping basic info for now.
        name = f.get("name", "Unknown")
        ftype = f.get("type", "Unknown")
        size = str(f.get("size", 0))
        # timestamp might be m_timestamp
        m_timestamp = f.get("m_timestamp", 0)
        ts_str = datetime.fromtimestamp(m_timestamp).strftime("%Y-%m-%d %H:%M:%S") if m_timestamp else ""
        
        table.add_row(name, ftype, size, ts_str)
        
    console.print(table)

def get_telemetry_cli(printer_id: str, granularity: int):
    token = get_valid_token()
    api = PrusaConnectAPI(token)
    uuid = resolve_printer_uuid(api, printer_id)
    
    data = api.get_telemetry(uuid, granularity=granularity)
    rprint(data)

def list_jobs(printer_id: str, limit: int):
    token = get_valid_token()
    api = PrusaConnectAPI(token)
    uuid = resolve_printer_uuid(api, printer_id)
    
    # api.get_job_history now supports limits.
    data = api.get_job_history(uuid, limit=limit)
    jobs = data.get("jobs", [])
    
    table = Table(title=f"Job History on {printer_id}")
    table.add_column("ID", style="cyan")
    table.add_column("State", style="magenta")
    table.add_column("File", style="green")
    table.add_column("Start", style="blue")
    table.add_column("Duration", style="yellow")
    
    for j in jobs[:limit]:
        job_id = str(j.get("id", ""))
        state = j.get("state", "Unknown")
        file_data = j.get("file", {})
        filename = file_data.get("name") if file_data else "Unknown"
        ts_start = j.get("start_ts")
        start_str = datetime.fromtimestamp(ts_start).strftime("%Y-%m-%d %H:%M:%S") if ts_start else ""
        duration = str(j.get("duration", 0))
        
        table.add_row(job_id, state, filename, start_str, duration)
        
    console.print(table)

def list_queue(printer_id: str):
    token = get_valid_token()
    api = PrusaConnectAPI(token)
    uuid = resolve_printer_uuid(api, printer_id)
    
    data = api.get_print_queue(uuid)
    queue_items = data.get("queue", [])
    
    table = Table(title=f"Print Queue on {printer_id}")
    table.add_column("Pos", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Ready", style="magenta")
    table.add_column("Added", style="blue")
    
    for q in queue_items:
        # Need to verify structure from queue.response.json if possible, but guessing standard fields
        pos = str(q.get("position", "?"))
        # File might be nested
        file_path = q.get("path", "Unknown") # Request had path, so maybe response has it too?
        # queue.response.json exists, I could check it.
        # But this is a good guess.
        ready = "Yes" if q.get("set_ready") else "No"
        ts_add = q.get("add_ts")
        added_str = datetime.fromtimestamp(ts_add).strftime("%Y-%m-%d %H:%M:%S") if ts_add else ""
        
        table.add_row(pos, file_path, ready, added_str)
        
    console.print(table)

def main():
    try:
        CliApp.run(Root)
    except Exception as e:
        rprint(f"[red]Error parsing arguments: {e}[/red]")
        sys.exit(1)

if __name__ == "__main__":
    main()
