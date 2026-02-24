"""Camera management commands."""

import pathlib
import sys
import typing

import cyclopts

from prusa.connect.client.cli import common, config

camera_app = cyclopts.App(name="camera", help="Camera management")

_NO_CAMERA = (
    "No camera ID provided and no default configured.\n"
    "Hint: Run 'prusactl camera list' to find a numeric ID, then "
    "'prusactl camera set-current <numeric-id>' to set the default."
)


@camera_app.command(name="list")
def camera_list():
    """List all cameras."""
    common.logger.debug("Command started", command="camera list")
    client = common.get_client()
    cameras = client.cameras.list()

    rows = [[c.name or "Unknown", str(c.id) if c.id else "N/A", c.token or "N/A", c.origin or "N/A"] for c in cameras]
    common.output_table(
        "Cameras",
        ["Name", "ID (Numeric)", "Token", "Origin"],
        rows,
        column_styles=["cyan", "magenta", "green", "blue"],
    )


def cameras_alias():
    """List all cameras (alias for 'camera list')."""
    camera_list()


@camera_app.command(name="snapshot")
def camera_snapshot(
    camera_id: typing.Annotated[str | None, cyclopts.Parameter(help="Camera ID (Numeric)")] = None,
    output: typing.Annotated[pathlib.Path | None, cyclopts.Parameter(help="Output file path for snapshot")] = None,
):
    """Take a snapshot from a camera."""
    common.logger.debug("Command started", command="camera snapshot", camera_id=camera_id, output=output)
    client = common.get_client()

    resolved_id = camera_id or config.settings.default_camera_id
    if not resolved_id:
        common.output_message(_NO_CAMERA, error=True)
        return

    # We look up the camera to get ID
    cameras = client.cameras.list()
    match = next((c for c in cameras if str(c.id) == camera_id or c.token == camera_id or c.name == camera_id), None)

    real_id = resolved_id
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
                common.output_message(f"Saved snapshot to {output}")
        else:
            common.output_message(f"Snapshot received: {len(data)} bytes")
    except Exception as e:
        if str(output) == "-":
            sys.stderr.write(f"Failed to get snapshot: {e}\n")
        else:
            common.output_message(f"Failed to get snapshot: {e}", error=True)


@camera_app.command(name="trigger")
def camera_trigger(
    camera_id: typing.Annotated[str | None, cyclopts.Parameter(help="Camera Token or ID (if mapped)")] = None,
):
    """Trigger a snapshot on a camera."""
    common.logger.debug("Command started", command="camera trigger", camera_id=camera_id)
    client = common.get_client()

    resolved_id = camera_id or config.settings.default_camera_id
    if not resolved_id:
        common.output_message(_NO_CAMERA, error=True)
        return

    # We look up to get token
    cameras = client.cameras.list()
    match = next(
        (c for c in cameras if str(c.id) == resolved_id or c.token == resolved_id or c.name == resolved_id), None
    )

    real_token = resolved_id
    if match:
        if match.token:
            real_token = match.token
        common.logger.debug("Resolved camera", name=match.name, token=real_token)

    try:
        if client.trigger_snapshot(real_token):
            common.output_message(f"Triggered snapshot for {camera_id}")
    except Exception as e:
        common.output_message(f"Failed to trigger snapshot: {e}", error=True)


@camera_app.command(name="move")
def camera_move(
    camera_id: typing.Annotated[str | None, cyclopts.Parameter(help="Camera Token or ID")] = None,
    direction: typing.Annotated[
        typing.Literal["LEFT", "RIGHT", "UP", "DOWN"] | None,
        cyclopts.Parameter(help="Direction: LEFT, RIGHT, UP, DOWN"),
    ] = None,
    angle: typing.Annotated[int, cyclopts.Parameter(help="Angle in degrees")] = 30,
):
    """Move a pan/tilt camera."""
    common.logger.debug("Command started", command="camera move", camera_id=camera_id, direction=direction)
    client = common.get_client()

    resolved_id = camera_id or config.settings.default_camera_id
    if not resolved_id:
        common.output_message(_NO_CAMERA, error=True)
        return

    if direction is None:
        common.output_message("A direction (LEFT, RIGHT, UP, or DOWN) must be specified", error=True)

    # Resolve token
    cameras = client.cameras.list()
    match = next(
        (c for c in cameras if str(c.id) == resolved_id or c.token == resolved_id or c.name == resolved_id), None
    )
    token = match.token if match and match.token else resolved_id

    try:
        cam_client = client.get_camera_client(token)
        cam_client.connect()
        cam_client.move(str(direction), angle)
        common.output_message(f"Sent {direction} move command to {camera_id}")
        cam_client.disconnect()
    except Exception as e:
        common.output_message(f"Failed to move camera: {e}", error=True)


@camera_app.command(name="adjust")
def camera_adjust(
    camera_id: typing.Annotated[str | None, cyclopts.Parameter(help="Camera Token or ID")] = None,
    brightness: typing.Annotated[int | None, cyclopts.Parameter(help="Brightness value")] = None,
    contrast: typing.Annotated[int | None, cyclopts.Parameter(help="Contrast value")] = None,
    saturation: typing.Annotated[int | None, cyclopts.Parameter(help="Saturation value")] = None,
):
    """Adjust camera image settings."""
    common.logger.debug("Command started", command="camera adjust", camera_id=camera_id)
    client = common.get_client()

    resolved_id = camera_id or config.settings.default_camera_id
    if not resolved_id:
        common.output_message(_NO_CAMERA, error=True)
        return

    # Resolve token
    cameras = client.cameras.list()
    match = next(
        (c for c in cameras if str(c.id) == resolved_id or c.token == resolved_id or c.name == resolved_id), None
    )
    token = match.token if match and match.token else resolved_id

    kwargs = {}
    if brightness is not None:
        kwargs["brightness"] = brightness
    if contrast is not None:
        kwargs["contrast"] = contrast
    if saturation is not None:
        kwargs["saturation"] = saturation

    if not kwargs:
        common.output_message("No adjustments provided. Use --brightness, --contrast, or --saturation.")
        return

    try:
        cam_client = client.get_camera_client(token)
        cam_client.connect()
        cam_client.adjust(**kwargs)
        common.output_message(f"Adjusted settings for {camera_id}")
        cam_client.disconnect()
    except Exception as e:
        common.output_message(f"Failed to adjust camera: {e}", error=True)


@camera_app.command(name="set-current")
def set_current_camera(camera_id: typing.Annotated[str, cyclopts.Parameter(help="Camera UUID")]):
    """Set the default camera ID for future commands."""
    config.settings.default_camera_id = camera_id
    config.save_json_config(config.settings)
    common.output_message(f"Successfully set default camera to {camera_id}")


@camera_app.command(name="show")
def camera_show(
    camera_id: typing.Annotated[str | None, cyclopts.Parameter(help="Camera Token or ID or Name")] = None,
    detailed: bool = False,
):
    """Show details for a specific camera."""
    common.logger.debug("Command started", command="camera show", camera_id=camera_id, detailed=detailed)
    client = common.get_client()

    resolved_id = camera_id or config.settings.default_camera_id
    if not resolved_id:
        common.output_message(_NO_CAMERA, error=True)
        return

    cameras = client.cameras.list()
    match = next(
        (c for c in cameras if str(c.id) == resolved_id or c.token == resolved_id or c.name == resolved_id), None
    )

    if not match:
        common.output_message(f"Camera '{camera_id}' not found.", error=True)
        sys.exit(1)

    if detailed and common.get_output_format() == "rich":
        from rich.panel import Panel
        from rich.pretty import Pretty

        common.console.print(Panel(Pretty(match), title=f"Camera: {match.name or 'Unknown'}"))
    else:
        rows = [
            ["Name", match.name or "N/A"],
            ["ID (Numeric)", str(match.id) if match.id else "N/A"],
            ["Token", match.token or "N/A"],
            ["Origin", match.origin or "N/A"],
        ]

        if match.config:
            if match.config.resolution:
                rows.append(["Resolution", f"{match.config.resolution.width}x{match.config.resolution.height}"])
            if match.config.firmware:
                rows.append(["Firmware", match.config.firmware])
            if match.config.model:
                rows.append(["Model", match.config.model])

        if match.printer_uuid:
            rows.append(["Printer UUID", match.printer_uuid])

        common.output_table(
            f"Camera: {match.name or 'Unknown'}",
            ["Property", "Value"],
            rows,
            column_styles=["bold cyan", None],
        )
