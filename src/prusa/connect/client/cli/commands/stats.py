"""Printer statistics commands."""

import datetime
import typing

import cyclopts
from rich.table import Table

from prusa.connect.client.cli import common, config

stats_app = cyclopts.App(name="stats", help="Printer statistics")
logger = common.logger


@stats_app.command(name="usage")
def stats_usage(
    printer_id: typing.Annotated[str | None, cyclopts.Parameter(help="Printer UUID")] = None,
    days: typing.Annotated[int, cyclopts.Parameter(help="Number of days to look back")] = 7,
    from_date: typing.Annotated[
        datetime.date | None, cyclopts.Parameter(name=["--from", "-f"], help="Start date")
    ] = None,
    to_date: typing.Annotated[datetime.date | None, cyclopts.Parameter(name=["--to", "-t"], help="End date")] = None,
):
    """Show printer usage statistics (printing vs not printing)."""
    resolved_id = printer_id or config.settings.default_printer_id
    if not resolved_id:
        common.console.print(
            "[red]No printer ID provided and no default configured.[/red]\n"
            "[dim]Hint: Run 'prusactl printer list' to find a UUID, then\n"
            "'prusactl printer set-current <uuid>' to set the default.[/dim]"
        )
        return

    client = common.get_client()
    if not from_date:
        from_date = datetime.date.today() - datetime.timedelta(days=days)
    if not to_date:
        to_date = datetime.date.today()

    try:
        stats = client.get_printer_usage_stats(resolved_id, from_time=from_date, to_time=to_date)
        table = Table(title=f"Usage Stats for {stats.printer_name} ({from_date} to {to_date})")
        table.add_column("Type", style="cyan")
        table.add_column("Value", style="magenta")

        for entry in stats.data:
            table.add_row(entry.name, str(entry.value))

        common.console.print(table)
    except Exception as e:
        common.console.print(f"[red]Error:[/red] {e}")


@stats_app.command(name="material")
def stats_material(
    printer_id: typing.Annotated[str | None, cyclopts.Parameter(help="Printer UUID")] = None,
    days: typing.Annotated[int, cyclopts.Parameter(help="Number of days to look back")] = 7,
    from_date: typing.Annotated[
        datetime.date | None, cyclopts.Parameter(name=["--from", "-f"], help="Start date")
    ] = None,
    to_date: typing.Annotated[datetime.date | None, cyclopts.Parameter(name=["--to", "-t"], help="End date")] = None,
):
    """Show material quantity statistics."""
    resolved_id = printer_id or config.settings.default_printer_id
    if not resolved_id:
        common.console.print(
            "[red]No printer ID provided and no default configured.[/red]\n"
            "[dim]Hint: Run 'prusactl printer list' to find a UUID, then "
            "'prusactl printer set-current <uuid>' to set the default.[/dim]"
        )
        return

    client = common.get_client()
    if not from_date:
        from_date = datetime.date.today() - datetime.timedelta(days=days)
    if not to_date:
        to_date = datetime.date.today()

    try:
        stats = client.get_printer_material_stats(resolved_id, from_time=from_date, to_time=to_date)

        table = Table(title=f"Material Stats for {stats.printer_name} ({from_date} to {to_date})")
        table.add_column("Material", style="cyan")
        table.add_column("Usage", style="magenta")

        if not stats.data:
            table.add_row("No data available", "")
        else:
            for entry in stats.data:
                if isinstance(entry, dict):
                    table.add_row(entry.get("name", "Unknown"), str(entry.get("value", "N/A")))
                else:
                    table.add_row("Raw Data", str(entry))

        common.console.print(table)
    except Exception as e:
        common.console.print(f"[red]Error:[/red] {e}")


@stats_app.command(name="jobs")
def stats_jobs(
    printer_id: typing.Annotated[str | None, cyclopts.Parameter(help="Printer UUID")] = None,
    days: typing.Annotated[int, cyclopts.Parameter(help="Number of days to look back")] = 7,
    from_date: typing.Annotated[
        datetime.date | None, cyclopts.Parameter(name=["--from", "-f"], help="Start date")
    ] = None,
    to_date: typing.Annotated[datetime.date | None, cyclopts.Parameter(name=["--to", "-t"], help="End date")] = None,
):
    """Show job success statistics."""
    resolved_id = printer_id or config.settings.default_printer_id
    if not resolved_id:
        common.console.print(
            "[red]No printer ID provided and no default configured.[/red]\n"
            "[dim]Hint: Run 'prusactl printer list' to find a UUID, then "
            "'prusactl printer set-current <uuid>' to set the default.[/dim]"
        )
        return

    client = common.get_client()
    if not from_date:
        from_date = datetime.date.today() - datetime.timedelta(days=days)
    if not to_date:
        to_date = datetime.date.today()

    try:
        stats = client.get_printer_jobs_success_stats(resolved_id, from_time=from_date, to_time=to_date)

        # Sort stats by JobStatus enum order
        stats.series.sort(key=lambda x: x.status)

        logger.debug("Job Stats", data=stats)
        table = Table(title=f"Job Success Stats for {stats.printer_name} ({from_date} to {to_date})")
        table.add_column("Status", style="cyan")

        for date in stats.date_axis:
            table.add_column(date, style="magenta")

        for series in stats.series:
            row = [series.status.name]
            row.extend(str(v) for v in series.data)
            table.add_row(*row)

        common.console.print(table)
    except Exception as e:
        common.console.print(f"[red]Error:[/red] {e}")


@stats_app.command(name="planned")
def stats_planned(
    printer_id: typing.Annotated[str | None, cyclopts.Parameter(help="Printer UUID")] = None,
    days: typing.Annotated[int, cyclopts.Parameter(help="Number of days to look back")] = 7,
    from_date: typing.Annotated[
        datetime.date | None, cyclopts.Parameter(name=["--from", "-f"], help="Start date")
    ] = None,
    to_date: typing.Annotated[datetime.date | None, cyclopts.Parameter(name=["--to", "-t"], help="End date")] = None,
):
    """Show planned tasks statistics."""
    resolved_id = printer_id or config.settings.default_printer_id
    if not resolved_id:
        common.console.print(
            "[red]No printer ID provided and no default configured.[/red]\n"
            "[dim]Hint: Run 'prusactl printer list' to find a UUID, then "
            "'prusactl printer set-current <uuid>' to set the default.[/dim]"
        )
        return

    client = common.get_client()
    if not from_date:
        from_date = datetime.date.today() - datetime.timedelta(days=days)
    if not to_date:
        to_date = datetime.date.today()

    try:
        stats = client.get_printer_planned_tasks_stats(resolved_id, from_time=from_date, to_time=to_date)
        table = Table(title=f"Planned Tasks for {stats.series.printer_name} ({from_date} to {to_date})")
        table.add_column("Hour (UTC)", style="cyan")
        table.add_column("Count", style="magenta")

        if stats.series and stats.series.data:
            for hour, count in stats.series.data:
                table.add_row(f"{hour:02d}:00", str(count))
        else:
            table.add_row("No data available", "")

        common.console.print(table)
    except Exception as e:
        common.console.print(f"[red]Error:[/red] {e}")
