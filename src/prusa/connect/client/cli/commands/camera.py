"""Camera management commands."""

import pathlib
import sys
import typing

import cyclopts
from rich import print as rprint
from rich.table import Table

from prusa.connect.client.cli import common, config

camera_app = cyclopts.App(name="camera", help="Camera management")


@camera_app.command(name="list")
def camera_list():
    """List all cameras."""
    common.logger.debug("Command started", command="camera list")
    client = common.get_client()
    cameras = client.cameras.list()

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
    common.console.print(table)


def camera_alias():
    """List all cameras (alias for 'camera list')."""
    camera_list()


@camera_app.command(name="snapshot")
def camera_snapshot(
    camera_id: typing.Annotated[str, cyclopts.Parameter(help="Camera ID (Numeric)")],
    output: typing.Annotated[pathlib.Path | None, cyclopts.Parameter(help="Output file path for snapshot")] = None,
):
    """Take a snapshot from a camera."""
    common.logger.debug("Command started", command="camera snapshot", camera_id=camera_id, output=output)
    client = common.get_client()

    # We look up the camera to get ID
    cameras = client.cameras.list()
    match = next((c for c in cameras if str(c.id) == camera_id or c.token == camera_id or c.name == camera_id), None)

    real_id = camera_id
    if match:
        if match.id:
            real_id = str(match.id)
        common.logger.debug("Resolved camera", name=match.name, id=real_id)

    try:
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
            sys.stderr.write(f"Failed to get snapshot: {e}\n")
        else:
            rprint(f"[red]Failed to get snapshot: {e}[/red]")


@camera_app.command(name="trigger")
def camera_trigger(
    camera_id: typing.Annotated[str, cyclopts.Parameter(help="Camera Token or ID (if mapped)")],
):
    """Trigger a snapshot on a camera."""
    common.logger.debug("Command started", command="camera trigger", camera_id=camera_id)
    client = common.get_client()

    # We look up to get token
    cameras = client.cameras.list()
    match = next((c for c in cameras if str(c.id) == camera_id or c.token == camera_id or c.name == camera_id), None)

    real_token = camera_id
    if match:
        if match.token:
            real_token = match.token
        common.logger.debug("Resolved camera", name=match.name, token=real_token)

    try:
        if client.trigger_snapshot(real_token):
            rprint(f"[green]Triggered snapshot for {camera_id}[/green]")
    except Exception as e:
        rprint(f"[red]Failed to trigger snapshot: {e}[/red]")


@camera_app.command(name="move")
def camera_move(
    camera_id: typing.Annotated[str, cyclopts.Parameter(help="Camera Token or ID")],
    direction: typing.Annotated[str, cyclopts.Parameter(help="Direction: LEFT, RIGHT, UP, DOWN")],
    angle: typing.Annotated[int, cyclopts.Parameter(help="Angle in degrees")] = 30,
):
    """Move a pan/tilt camera."""
    common.logger.debug("Command started", command="camera move", camera_id=camera_id, direction=direction)
    client = common.get_client()

    # Resolve token
    cameras = client.cameras.list()
    match = next((c for c in cameras if str(c.id) == camera_id or c.token == camera_id or c.name == camera_id), None)
    token = match.token if match and match.token else camera_id

    try:
        cam_client = client.get_camera_client(token)
        cam_client.connect()
        cam_client.move(direction, angle)
        rprint(f"[green]Sent {direction} move command to {camera_id}[/green]")
        cam_client.disconnect()
    except Exception as e:
        rprint(f"[red]Failed to move camera: {e}[/red]")


@camera_app.command(name="adjust")
def camera_adjust(
    camera_id: typing.Annotated[str, cyclopts.Parameter(help="Camera Token or ID")],
    brightness: typing.Annotated[int | None, cyclopts.Parameter(help="Brightness value")] = None,
    contrast: typing.Annotated[int | None, cyclopts.Parameter(help="Contrast value")] = None,
    saturation: typing.Annotated[int | None, cyclopts.Parameter(help="Saturation value")] = None,
):
    """Adjust camera image settings."""
    common.logger.debug("Command started", command="camera adjust", camera_id=camera_id)
    client = common.get_client()

    # Resolve token
    cameras = client.cameras.list()
    match = next((c for c in cameras if str(c.id) == camera_id or c.token == camera_id or c.name == camera_id), None)
    token = match.token if match and match.token else camera_id

    kwargs = {}
    if brightness is not None:
        kwargs["brightness"] = brightness
    if contrast is not None:
        kwargs["contrast"] = contrast
    if saturation is not None:
        kwargs["saturation"] = saturation

    if not kwargs:
        rprint("[yellow]No adjustments provided. Use --brightness, --contrast, or --saturation.[/yellow]")
        return

    try:
        cam_client = client.get_camera_client(token)
        cam_client.connect()
        cam_client.adjust(**kwargs)
        rprint(f"[green]Adjusted settings for {camera_id}[/green]")
        cam_client.disconnect()
    except Exception as e:
        rprint(f"[red]Failed to adjust camera: {e}[/red]")


@camera_app.command(name="set-current")
def set_current_camera(camera_id: typing.Annotated[str, cyclopts.Parameter(help="Camera UUID")]):
    """Set the default camera ID for future commands."""
    config.settings.default_camera_id = camera_id
    config.save_json_config(config.settings)
    rprint(f"[green]Successfully set default camera to {camera_id}[/green]")


@camera_app.command(name="show")
def camera_show(
    camera_id: typing.Annotated[str, cyclopts.Parameter(help="Camera Token or ID or Name")],
    detailed: bool = False,
):
    """Show details for a specific camera."""
    common.logger.debug("Command started", command="camera show", camera_id=camera_id, detailed=detailed)
    client = common.get_client()

    cameras = client.cameras.list()
    match = next((c for c in cameras if str(c.id) == camera_id or c.token == camera_id or c.name == camera_id), None)

    if not match:
        rprint(f"[red]Camera '{camera_id}' not found.[/red]")
        sys.exit(1)

    if detailed:
        from rich.panel import Panel
        from rich.pretty import Pretty

        common.console.print(Panel(Pretty(match), title=f"Camera: {match.name or 'Unknown'}"))
    else:
        table = Table(show_header=False, box=None)
        table.add_column("Property", style="bold cyan")
        table.add_column("Value")

        table.add_row("Name", match.name or "N/A")
        table.add_row("ID (Numeric)", str(match.id) if match.id else "N/A")
        table.add_row("Token", match.token or "N/A")
        table.add_row("Origin", match.origin or "N/A")

        if match.config:
            if match.config.resolution:
                table.add_row("Resolution", f"{match.config.resolution.width}x{match.config.resolution.height}")
            if match.config.firmware:
                table.add_row("Firmware", match.config.firmware)
            if match.config.model:
                table.add_row("Model", match.config.model)

        if match.printer_uuid:
            table.add_row("Printer UUID", match.printer_uuid)

        common.console.print(table)
