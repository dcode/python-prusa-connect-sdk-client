"""Printer statistics commands."""

import datetime
import typing

import cyclopts

from prusa.connect.client.cli import common, config

stats_app = cyclopts.App(name="stats", help="Printer statistics")
logger = common.logger

_NO_PRINTER = (
    "No printer ID provided and no default configured.\n"
    "Hint: Run 'prusactl printer list' to find a UUID, then "
    "'prusactl printer set-current <uuid>' to set the default."
)


@stats_app.command(name="usage")
def stats_usage(
    printer_id: typing.Annotated[str | None, cyclopts.Parameter(help="Printer UUID")] = None,
    days: typing.Annotated[int, cyclopts.Parameter(help="Number of days to look back")] = 7,
    from_date: typing.Annotated[
        datetime.date | None, cyclopts.Parameter(name=["--from", "-f"], help="Start date")
    ] = None,
    to_date: typing.Annotated[datetime.date | None, cyclopts.Parameter(name=["--to", "-t"], help="End date")] = None,
    seconds: typing.Annotated[bool, cyclopts.Parameter(help="Output duration in seconds")] = False,
):
    """Show printer usage statistics (printing vs not printing)."""
    resolved_id = printer_id or config.settings.default_printer_id
    if not resolved_id:
        common.output_message(_NO_PRINTER, error=True)
        return

    client = common.get_client()
    if not from_date:
        from_date = datetime.date.today() - datetime.timedelta(days=days)
    if not to_date:
        to_date = datetime.date.today()

    try:
        stats = client.get_printer_usage_stats(resolved_id, from_time=from_date, to_time=to_date)
        rows = [
            [entry.name, str(entry.duration) if not seconds else str(entry.duration.total_seconds())]
            for entry in stats.data
        ]
        common.output_table(
            f"Usage Stats for {stats.printer_name} ({from_date} to {to_date})",
            ["Type", "Duration"],
            rows,
            column_styles=["cyan", "magenta"],
        )
    except Exception as e:
        common.output_message(f"Error: {e}", error=True)


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
        common.output_message(_NO_PRINTER, error=True)
        return

    client = common.get_client()
    if not from_date:
        from_date = datetime.date.today() - datetime.timedelta(days=days)
    if not to_date:
        to_date = datetime.date.today()

    try:
        stats = client.get_printer_material_stats(resolved_id, from_time=from_date, to_time=to_date)

        rows = []
        if not stats.data:
            rows.append(["No data available", ""])
        else:
            for entry in stats.data:
                if isinstance(entry, dict):
                    rows.append([entry.get("name", "Unknown"), str(entry.get("value", "N/A"))])
                else:
                    rows.append(["Raw Data", str(entry)])

        common.output_table(
            f"Material Stats for {stats.printer_name} ({from_date} to {to_date})",
            ["Material", "Usage"],
            rows,
            column_styles=["cyan", "magenta"],
        )
    except Exception as e:
        common.output_message(f"Error: {e}", error=True)


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
        common.output_message(_NO_PRINTER, error=True)
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
        columns = ["Status", *list(stats.date_axis)]
        rows = []
        for series in stats.series:
            row = [series.status.name] + [str(v) for v in series.data]
            rows.append(row)

        common.output_table(
            f"Job Success Stats for {stats.printer_name} ({from_date} to {to_date})",
            columns,
            rows,
            column_styles=["cyan"] + ["magenta"] * len(stats.date_axis),
        )
    except Exception as e:
        common.output_message(f"Error: {e}", error=True)


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
        common.output_message(_NO_PRINTER, error=True)
        return

    client = common.get_client()
    if not from_date:
        from_date = datetime.date.today() - datetime.timedelta(days=days)
    if not to_date:
        to_date = datetime.date.today()

    try:
        stats = client.get_printer_planned_tasks_stats(resolved_id, from_time=from_date, to_time=to_date)

        rows = []
        if stats.series and stats.series.data:
            for hour, count in stats.series.data:
                rows.append([f"{hour:02d}:00", str(count)])
        else:
            rows.append(["No data available", ""])

        common.output_table(
            f"Planned Tasks for {stats.series.printer_name} ({from_date} to {to_date})",
            ["Hour (UTC)", "Count"],
            rows,
            column_styles=["cyan", "magenta"],
        )
    except Exception as e:
        common.output_message(f"Error: {e}", error=True)
