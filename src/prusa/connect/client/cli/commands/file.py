"""File management commands."""

import os
import typing

import cyclopts
from rich.table import Table

from prusa.connect.client.cli import common, config

file_app = cyclopts.App(name="file", help="File management (Connect/Team level)")


def file_list(
    team_id: typing.Annotated[int | None, cyclopts.Parameter(help="Team ID to list files for")] = None,
):
    """List files in a team storage."""
    client = common.get_client()
    resolved_team_id = team_id or config.settings.default_team_id

    if not resolved_team_id:
        teams = client.get_teams()
        if not teams:
            common.console.print("[red]No teams found.[/red]")
            return
        resolved_team_id = teams[0].id
        common.console.print(
            f"[yellow]No team ID provided. Using first team: {teams[0].name} ({resolved_team_id})[/yellow]"
        )

    files = client.get_file_list(resolved_team_id)

    table = Table(title=f"Files for Team {resolved_team_id}")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Size", style="magenta")
    table.add_column("Hash", style="blue")

    for f in files:
        size_str = f"{f.size.human_readable()}" if f.size else "N/A"
        table.add_row(f.name or "N/A", f.type or "N/A", size_str, f.hash or "N/A")

    common.console.print(table)


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
        teams = client.get_teams()
        if not teams:
            common.console.print("[red]No teams found.[/red]")
            return
        resolved_team_id = teams[0].id

    file_path = os.path.abspath(path)
    if not os.path.exists(file_path):
        common.console.print(f"[red]File not found: {path}[/red]")
        return

    filename = os.path.basename(file_path)
    size = os.path.getsize(file_path)

    common.console.print(f"Initiating upload for [cyan]{filename}[/cyan] ({size} bytes)...")
    try:
        status = client.initiate_team_upload(resolved_team_id, destination, filename, size)
        upload_id = status.id
        common.console.print(f"Upload initiated. ID: [magenta]{upload_id}[/magenta]. Uploading data...")

        with open(file_path, "rb") as f:
            data = f.read()

        content_type = "application/octet-stream"
        if filename.endswith(".bgcode"):
            content_type = "application/x-bgcode"
        elif filename.endswith(".gcode"):
            content_type = "text/x.gcode"

        client.upload_team_file(resolved_team_id, upload_id, data, content_type=content_type)
        common.console.print("[green]Upload successful![/green]")
    except Exception as e:
        common.console.print(f"[red]Upload failed: {e}[/red]")


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
        teams = client.get_teams()
        if not teams:
            common.console.print("[red]No teams found.[/red]")
            return
        resolved_team_id = teams[0].id

    common.console.print(f"Downloading file with hash [cyan]{file_hash}[/cyan]...")
    try:
        data = client.download_team_file(resolved_team_id, file_hash)

        dest_path = output or file_hash
        with open(dest_path, "wb") as f:
            f.write(data)

        common.console.print(f"[green]Downloaded to {dest_path}[/green]")
    except Exception as e:
        common.console.print(f"[red]Download failed: {e}[/red]")


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
        teams = client.get_teams()
        if not teams:
            common.console.print("[red]No teams found.[/red]")
            return
        resolved_team_id = teams[0].id

    try:
        file = client.get_team_file(resolved_team_id, file_hash)

        table = Table(title=f"File Details: {file.name}")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Name", file.name)
        table.add_row("Type", getattr(file, "type", "N/A"))
        if getattr(file, "size", None) is not None:
            size_val = typing.cast("int", file.size)
            size_str = f"{size_val / 1024 / 1024:.2f} MB"
            table.add_row("Size", size_str)
        if getattr(file, "hash", None):
            table.add_row("Hash", file.hash)

        common.console.print(table)

        if detailed:
            import json

            common.console.print("\n[bold]Detailed Information:[/bold]")
            detail_table = Table(show_header=False, box=None)
            for k, v in file.model_dump(mode="json").items():
                if v is not None and k not in ["name", "type", "size", "hash"]:
                    val_str = json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                    detail_table.add_row(f"[cyan]{k.title().replace('_', ' ')}[/cyan]:", val_str)
            common.console.print(detail_table)

    except Exception as e:
        common.console.print(f"[red]Failed to fetch file details: {e}[/red]")
