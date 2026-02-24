"""File management commands."""

import json
import os
import typing

import cyclopts

from prusa.connect.client.cli import common, config

file_app = cyclopts.App(name="file", help="File management (Connect/Team level)")


@file_app.command(name="list")
def file_list(
    team_id: typing.Annotated[int | None, cyclopts.Parameter(help="Team ID to list files for")] = None,
):
    """List files in a team storage."""
    client = common.get_client()
    resolved_team_id = team_id or config.settings.default_team_id

    if not resolved_team_id:
        teams = client.teams.list_teams()
        if not teams:
            common.output_message("No teams found.", error=True)
            return
        resolved_team_id = teams[0].id
        common.output_message(f"No team ID provided. Using first team: {teams[0].name} ({resolved_team_id})")

    files = client.get_file_list(resolved_team_id)

    rows = []
    for f in files:
        size_str = f"{f.size.human_readable()}" if f.size else "N/A"
        rows.append([f.name or "N/A", f.type or "N/A", size_str, f.hash or "N/A"])

    common.output_table(
        f"Files for Team {resolved_team_id}",
        ["Name", "Type", "Size", "Hash"],
        rows,
        column_styles=["cyan", "green", "magenta", "blue"],
    )


def files_alias(
    team_id: typing.Annotated[int | None, cyclopts.Parameter(help="Team ID to list files for")] = None,
):
    """List files (alias for 'file list')."""
    file_list(team_id=team_id)


@file_app.command(name="upload")
def file_upload(
    path: typing.Annotated[str, cyclopts.Parameter(help="Local path to file")],
    team_id: typing.Annotated[int | None, cyclopts.Parameter(help="Team ID")] = None,
    destination: typing.Annotated[str, cyclopts.Parameter(help="Destination folder")] = "/",
):
    """Upload a file to Connect."""
    client = common.get_client()
    resolved_team_id = team_id or config.settings.default_team_id
    if not resolved_team_id:
        teams = client.teams.list_teams()
        if not teams:
            common.output_message("No teams found.", error=True)
            return
        resolved_team_id = teams[0].id

    file_path = os.path.abspath(path)
    if not os.path.exists(file_path):
        common.output_message(f"File not found: {path}", error=True)
        return

    filename = os.path.basename(file_path)
    size = os.path.getsize(file_path)

    common.output_message(f"Initiating upload for {filename} ({size} bytes)...")
    try:
        status = client.initiate_team_upload(resolved_team_id, destination, filename, size)
        upload_id = status.id
        common.output_message(f"Upload initiated. ID: {upload_id}. Uploading data...")

        with open(file_path, "rb") as f:
            data = f.read()

        content_type = "application/octet-stream"
        if filename.endswith(".bgcode"):
            content_type = "application/x-bgcode"
        elif filename.endswith(".gcode"):
            content_type = "text/x.gcode"

        client.upload_team_file(resolved_team_id, upload_id, data, content_type=content_type)
        common.output_message("Upload successful!")
    except Exception as e:
        common.output_message(f"Upload failed: {e}", error=True)


@file_app.command(name="download")
def file_download(
    file_hash: typing.Annotated[str, cyclopts.Parameter(help="File hash to download")],
    team_id: typing.Annotated[int | None, cyclopts.Parameter(help="Team ID")] = None,
    output: typing.Annotated[str | None, cyclopts.Parameter(help="Optional output path/filename")] = None,
):
    """Download a file from Connect."""
    client = common.get_client()
    resolved_team_id = team_id or config.settings.default_team_id
    if not resolved_team_id:
        teams = client.teams.list_teams()
        if not teams:
            common.output_message("No teams found.", error=True)
            return
        resolved_team_id = teams[0].id

    common.output_message(f"Downloading file with hash {file_hash}...")
    try:
        data = client.download_team_file(resolved_team_id, file_hash)

        dest_path = output or file_hash
        with open(dest_path, "wb") as f:
            f.write(data)

        common.output_message(f"Downloaded to {dest_path}")
    except Exception as e:
        common.output_message(f"Download failed: {e}", error=True)


@file_app.command(name="show")
def file_show(
    file_hash: typing.Annotated[str, cyclopts.Parameter(help="File hash to show")],
    team_id: typing.Annotated[int | None, cyclopts.Parameter(help="Team ID")] = None,
    detailed: typing.Annotated[
        bool, cyclopts.Parameter(name=["--detailed", "-d"], help="Show detailed information about the file")
    ] = False,
):
    """Show detailed information for a specific file."""
    client = common.get_client()
    resolved_team_id = team_id or config.settings.default_team_id
    if not resolved_team_id:
        teams = client.teams.list_teams()
        if not teams:
            common.output_message("No teams found.", error=True)
            return
        resolved_team_id = teams[0].id

    try:
        file = client.get_team_file(resolved_team_id, file_hash)

        rows: list[list[str]] = [["Name", file.name], ["Type", getattr(file, "type", "N/A")]]
        if getattr(file, "size", None) is not None:
            size_val = typing.cast("int", file.size)
            rows.append(["Size", f"{size_val / 1024 / 1024:.2f} MB"])
        if getattr(file, "hash", None):
            rows.append(["Hash", file.hash])

        common.output_table(
            f"File Details: {file.name}",
            ["Property", "Value"],
            rows,
            column_styles=["cyan", "green"],
        )

        if detailed:
            detail_rows = []
            for k, v in file.model_dump(mode="json").items():
                if v is not None and k not in ["name", "type", "size", "hash"]:
                    val_str = json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                    detail_rows.append([k.title().replace("_", " "), val_str])
            if detail_rows:
                common.output_table(
                    "Detailed Information",
                    ["Field", "Value"],
                    detail_rows,
                    column_styles=["cyan", None],
                )

    except Exception as e:
        common.output_message(f"Failed to fetch file details: {e}", error=True)
