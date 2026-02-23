"""Job management commands."""

import datetime
import typing

import cyclopts
from rich import print as rprint
from rich.table import Table

from prusa.connect.client.cli import common, config

job_app = cyclopts.App(name="job", help="Job management")


@job_app.command(name="list")
def job_list(
    team: typing.Annotated[int | None, cyclopts.Parameter(name="--team", help="Filter by Team ID")] = None,
    printer: typing.Annotated[str | None, cyclopts.Parameter(name="--printer", help="Filter by Printer UUID")] = None,
    state: typing.Annotated[
        list[str] | None, cyclopts.Parameter(name="--state", help="Filter by job state (e.g. PRINTING, FINISHED)")
    ] = None,
    limit: typing.Annotated[int | None, cyclopts.Parameter(name="--limit", help="Limit number of jobs")] = None,
):
    """List job history.

    If no filters provided, lists jobs for all available printers (aggregated).
    """
    common.logger.debug("Command started", command="job list", team=team, printer=printer, state=state, limit=limit)
    client = common.get_client()

    all_jobs = []

    if printer:
        # Get jobs for specific printer
        all_jobs.extend(client.get_printer_jobs(printer, state=state, limit=limit))
    elif team:
        # Get jobs for specific team
        all_jobs.extend(client.get_team_jobs(team, state=state, limit=limit))
    else:
        # Aggregation mode: Get jobs from ALL printers (cached)
        # This is preferred over iterating teams if we want "my printers" context
        try:
            printers = client.printers.list_printers()
            for p in printers:
                if not p.uuid:
                    continue
                try:
                    # We fetch 'limit' items from EACH printer to ensure we have enough candidates for global sort
                    # If limit is None, we fetch default page
                    p_jobs = client.get_printer_jobs(p.uuid, state=state, limit=limit)
                    all_jobs.extend(p_jobs)
                except Exception as e:
                    common.logger.warning(f"Failed to fetch jobs for printer {p.name}", error=str(e))
        except Exception as e:
            common.logger.error("Failed to fetch printer list for aggregation", error=str(e))

    # Sort by 'end' time (descending) to show most recent first
    # Fallback to 'start' or 'id' if 'end' is missing
    def sort_key(j):
        # We want descending order, so we return a tuple that compares correctly
        # Use 0 as fallback for timestamps if missing
        return (j.end or 0, j.start or 0, j.id or 0)

    all_jobs.sort(key=sort_key, reverse=True)

    # Apply global limit
    if limit is not None:
        all_jobs = all_jobs[:limit]

    table = Table(title="Jobs")
    table.add_column("ID", style="cyan")
    table.add_column("Printer", style="magenta")
    table.add_column("State", style="green")
    table.add_column("Name", style="blue")
    table.add_column("Progress", style="yellow")
    table.add_column("Ended", style="dim")

    for j in all_jobs:
        # Format timestamp
        ended_str = "N/A"
        if j.end:
            ended_str = datetime.datetime.fromtimestamp(j.end).strftime("%Y-%m-%d %H:%M")
        elif j.state == "PRINTING":
            ended_str = "In Progress"

        table.add_row(
            str(j.id),
            j.printer_uuid or "Unknown",
            j.state.name,
            j.file.name if j.file else "Unknown",
            f"{j.progress}%" if j.progress is not None else "N/A",
            ended_str,
        )

    common.console.print(table)


def jobs_alias(
    team: typing.Annotated[int | None, cyclopts.Parameter(name="--team", help="Filter by Team ID")] = None,
    printer: typing.Annotated[str | None, cyclopts.Parameter(name="--printer", help="Filter by Printer UUID")] = None,
    state: typing.Annotated[list[str] | None, cyclopts.Parameter(name="--state", help="Filter by job state")] = None,
    limit: typing.Annotated[int | None, cyclopts.Parameter(name="--limit", help="Limit number of jobs")] = None,
):
    """List jobs (alias for 'job list')."""
    job_list(team=team, printer=printer, state=state, limit=limit)


@job_app.command(name="queued")
def job_queued(
    printer: typing.Annotated[str | None, cyclopts.Parameter(name="--printer", help="Filter by Printer UUID")] = None,
):
    """List queued jobs (pending)."""
    common.logger.debug("Command started", command="job queued", printer=printer)
    client = common.get_client()

    all_jobs = []

    if printer:
        try:
            all_jobs.extend(client.get_printer_queue(printer))
        except Exception as e:
            rprint(f"[red]Failed to fetch queue for {printer}: {e}[/red]")
    else:
        # Aggregate from all printers
        try:
            printers = client.printers.list_printers()
            for p in printers:
                if not p.uuid:
                    continue
                try:
                    q_jobs = client.get_printer_queue(p.uuid)
                    all_jobs.extend(q_jobs)
                except Exception as e:
                    common.logger.warning(f"Failed to fetch queue for printer {p.name}", error=str(e))
        except Exception as e:
            rprint(f"[red]Failed to fetch printer list: {e}[/red]")

    # Sort by creation/id (ascending for queue usually? or purely by order returned?)
    # Usually queues are FIFO, but aggregation might mix them.
    # We'll trust the order or sort by ID/date if available.
    # For now, let's keep them somewhat creation-ordered if possible.

    table = Table(title="Job Queue")
    table.add_column("ID", style="cyan")
    table.add_column("Printer", style="magenta")
    table.add_column("State", style="green")
    table.add_column("Name", style="blue")
    table.add_column("Source", style="dim")

    for j in all_jobs:
        source = "Unknown"
        if j.source_info:
            source = j.source_info.public_name or j.source_info.first_name or "Unknown"

        table.add_row(str(j.id), j.printer_uuid or "Unknown", j.state, j.file.name if j.file else "Unknown", source)

    if not all_jobs:
        rprint("[yellow]No jobs in queue.[/yellow]")
    else:
        common.console.print(table)


@job_app.command(name="show")
def job_show(
    job_id: typing.Annotated[int, cyclopts.Parameter(help="Job ID")],
    printer: typing.Annotated[str | None, cyclopts.Parameter(name="--printer", help="Printer UUID")] = None,
    detailed: typing.Annotated[
        bool, cyclopts.Parameter(name=["--detailed", "-d"], help="Show detailed information about the job")
    ] = False,
):
    """Show detailed job information including cancelable objects."""
    common.logger.debug("Command started", command="job show", job_id=job_id, printer=printer)
    client = common.get_client()
    resolved_printer_id = printer or config.settings.default_printer_id
    if not resolved_printer_id:
        rprint("[red]Printer UUID is required. Provide --printer or set a default.[/red]")
        return
    try:
        job = client.get_job(resolved_printer_id, job_id)

        # Basic Info
        rprint(f"[bold cyan]Job {job.id}[/bold cyan]")
        rprint(f"State: [green]{job.state}[/green]")
        if job.file:
            rprint(f"File: {job.file.name}")
        if job.progress is not None:
            rprint(f"Progress: {job.progress}%")
        if job.time_printing:
            rprint(f"Time Printing: {job.time_printing}s")

        # Cancelable Objects
        if job.cancelable_objects:
            rprint("\n[bold]Cancelable Objects:[/bold]")
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("ID", style="cyan", justify="right")
            table.add_column("Name", style="white")

            for obj in job.cancelable_objects:
                table.add_row(str(obj.id), obj.name)

            common.console.print(table)
        else:
            rprint("\n[dim]No cancelable objects found for this job.[/dim]")

        if detailed:
            import json

            rprint("\n[bold]Detailed Information:[/bold]")
            detail_table = Table(show_header=False, box=None)
            for k, v in job.model_dump(mode="json").items():
                if v is not None and k not in [
                    "id",
                    "state",
                    "file",
                    "progress",
                    "time_printing",
                    "cancelable_objects",
                ]:
                    val_str = json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                    detail_table.add_row(f"[cyan]{k.title().replace('_', ' ')}[/cyan]:", val_str)
            common.console.print(detail_table)

    except Exception as e:
        rprint(f"[red]Failed to fetch job details: {e}[/red]")
