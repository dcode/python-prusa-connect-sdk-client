"""Camera management commands.

This module provides CLI commands for interacting with and managing cameras
associated with Prusa Connect. It includes functionality for listing cameras,
taking snapshots, moving pan/tilt cameras, adjusting image settings, and
opening WebRTC camera streams.
"""

import contextlib
import pathlib
import sys
import typing
from importlib import resources

import cyclopts
import structlog

from prusa.connect.client.cli import common, config

camera_app = cyclopts.App(name="camera", help="Camera management")

logger = structlog.get_logger(__name__)

_NO_CAMERA = (
    "No camera ID provided and no default configured.\n"
    "Hint: Run 'prusactl camera list' to find a numeric ID, then "
    "'prusactl camera set-current <numeric-id>' to set the default."
)


@camera_app.command(name="list")
def camera_list():
    """List all cameras.

    Returns:
        None
    """
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
    """List all cameras (alias for 'camera list').

    Returns:
        None
    """
    camera_list()


@camera_app.command(name="snapshot")
def camera_snapshot(
    camera_id: typing.Annotated[str | None, cyclopts.Parameter(help="Camera ID (Numeric)")] = None,
    output: typing.Annotated[pathlib.Path | None, cyclopts.Parameter(help="Output file path for snapshot")] = None,
):
    """Take a snapshot from a camera.

    Args:
        camera_id (str | None, optional): Camera ID (Numeric). Defaults to None.
        output (pathlib.Path | None, optional): Output file path for snapshot. Defaults to None.

    Returns:
        None

    Raises:
        Exception: If fetching or saving the snapshot fails.
    """
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
    """Trigger a snapshot on a camera.

    Args:
        camera_id (str | None, optional): Camera Token or ID (if mapped). Defaults to None.

    Returns:
        None

    Raises:
        Exception: If triggering the snapshot fails.
    """
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
    """Move a pan/tilt camera.

    Args:
        camera_id (str | None, optional): Camera Token or ID. Defaults to None.
        direction (typing.Literal["LEFT", "RIGHT", "UP", "DOWN"] | None, optional): Movement
            direction. Defaults to None.
        angle (int, optional): Angle in degrees. Defaults to 30.

    Returns:
        None

    Raises:
        Exception: If the camera move command fails.
    """
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
    """Adjust camera image settings.

    Args:
        camera_id (str | None, optional): Camera Token or ID. Defaults to None.
        brightness (int | None, optional): Brightness value. Defaults to None.
        contrast (int | None, optional): Contrast value. Defaults to None.
        saturation (int | None, optional): Saturation value. Defaults to None.

    Returns:
        None

    Raises:
        Exception: If the camera adjustments fail.
    """
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
    """Set the default camera ID for future commands.

    Args:
        camera_id (str): Camera UUID to be set as default.

    Returns:
        None
    """
    config.settings.default_camera_id = camera_id
    config.save_json_config(config.settings)
    common.output_message(f"Successfully set default camera to {camera_id}")


@camera_app.command(name="webrtc")
def camera_webrtc(
    camera_id: typing.Annotated[str | None, cyclopts.Parameter(help="Camera Token or ID")] = None,
    output: typing.Annotated[
        pathlib.Path | None, cyclopts.Parameter(help="Path to save the HTML stream player to")
    ] = None,
):
    """Generate and open a WebRTC player for the camera stream.

    This command creates a local HTML file containing a WebRTC player pre-configured
    with the necessary connection details (Camera Token and JWT Token) to stream
    low-latency video directly from Prusa Connect. It then attempts to open this
    player in your default web browser.

    The WebRTC stream connects directly to the Prusa Connect signaling server and
    establishes a peer-to-peer connection for video delivery.

    Args:
        camera_id (str | None, optional): The Token, UUID, or configured name of the
            camera. If omitted, the default camera ID from settings is used.
        output (pathlib.Path | None, optional): File path where the generated HTML
            player should be saved. If omitted, a temporary file is created.

    Returns:
        None

    Raises:
        Exception: Broad exceptions during protobuf loading are caught and logged
            as errors without propagating.
    """
    import webbrowser

    common.logger.debug("Command started", command="camera webrtc", camera_id=camera_id)
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

    # Get JWT Token
    jwt_token = ""
    # We reach into private credentials safely per SDK usage
    if hasattr(client, "_credentials") and hasattr(client._credentials, "tokens"):
        jwt_token = client._credentials.tokens.access_token.raw_token

    # Load Template
    template_path = resources.files("prusa.connect.client.cli.templates") / "webrtc_template.html"

    if not template_path.is_file():
        common.output_message(f"Missing template file: {template_path}", error=True)
        return

    try:
        # Load Proto Definition from the package install (wheel)
        logger.debug(
            "List package resources of prusa.connect.client",
            resources=list(resources.files("prusa.connect.client").iterdir()),
        )
        if hasattr(resources.files("prusa.connect.client"), "joinpath"):
            logger.debug("Using joinpath", resources=resources.files("prusa.connect.client"))
            proto_path = resources.files("prusa.connect.client").joinpath("camera_v2.proto")
        else:
            logger.debug("Using pathlib style", resources=resources.files("prusa.connect.client"))
            proto_path = resources.files("prusa.connect.client") / "camera_v2.proto"

        logger.debug("Proto path", proto_path=proto_path, is_file=proto_path.is_file())
        if not proto_path.is_file():
            # Fallback for local development tree
            repo_root = pathlib.Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent
            proto_path = repo_root / "proto" / "prusa" / "connect" / "client" / "camera_v2.proto"
            logger.debug("Dev Proto path", repo_root=repo_root, proto_path=proto_path, is_file=proto_path.is_file())
            if not proto_path.is_file():
                common.output_message("Missing proto definition: camera_v2.proto", error=True)
                return
        proto_content = proto_path.read_text("utf-8")
    except Exception as e:
        common.output_message(f"Failed to load camera_v2.proto: {e}", error=True)
        return

    html_content = template_path.read_text("utf-8")

    # Escape backticks for javascript template literal
    proto_content = proto_content.replace("`", "\\`")

    html_content = html_content.replace("{{ CAMERA_TOKEN }}", token)
    html_content = html_content.replace("{{ JWT_TOKEN }}", jwt_token)
    html_content = html_content.replace("{{ PROTOBUF_DEFINITION }}", proto_content)

    if output:
        output.write_text(html_content, "utf-8")
        uri = output.absolute().as_uri()
        common.output_message(f"Saved WebRTC player to {uri}")
        common.output_message("Opening WebRTC player in browser...")
        webbrowser.open(uri)

    else:
        # Save to temp file and open
        import tempfile

        temp_file = pathlib.Path(tempfile.gettempdir()) / f"prusa_webrtc_{token}.html"
        temp_file.write_text(html_content, "utf-8")
        common.output_message(f"Saved WebRTC player to {temp_file.absolute()}")
        with contextlib.suppress(Exception):
            webbrowser.open(temp_file.absolute().as_uri())


@camera_app.command(name="show")
def camera_show(
    camera_id: typing.Annotated[str | None, cyclopts.Parameter(help="Camera Token or ID or Name")] = None,
    detailed: bool = False,
):
    """Show details for a specific camera.

    Args:
        camera_id (str | None, optional): Camera Token, ID, or Name. Defaults to None.
        detailed (bool, optional): Whether to show detailed output. Defaults to False.

    Returns:
        None
    """
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
