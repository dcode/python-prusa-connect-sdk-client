"""Job management commands."""

import datetime
import typing

import cyclopts

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
        try:
            printers = client.printers.list_printers()
            for p in printers:
                if not p.uuid:
                    continue
                try:
                    p_jobs = client.get_printer_jobs(p.uuid, state=state, limit=limit)
                    all_jobs.extend(p_jobs)
                except Exception as e:
                    common.logger.warning(f"Failed to fetch jobs for printer {p.name}", error=str(e))
        except Exception as e:
            common.logger.error("Failed to fetch printer list for aggregation", error=str(e))

    # Sort by 'end' time (descending) to show most recent first
    def sort_key(j):
        return (j.end or 0, j.start or 0, j.id or 0)

    all_jobs.sort(key=sort_key, reverse=True)

    if limit is not None:
        all_jobs = all_jobs[:limit]

    rows = []
    for j in all_jobs:
        ended_str = "N/A"
        if j.end:
            ended_str = datetime.datetime.fromtimestamp(j.end).strftime("%Y-%m-%d %H:%M")
        elif j.state == "PRINTING":
            ended_str = "In Progress"

        rows.append(
            [
                str(j.id),
                j.printer_uuid or "Unknown",
                j.state.name,
                j.file.name if j.file else "Unknown",
                f"{j.progress}%" if j.progress is not None else "N/A",
                ended_str,
            ]
        )

    common.output_table(
        "Jobs",
        ["ID", "Printer", "State", "Name", "Progress", "Ended"],
        rows,
        column_styles=["cyan", "magenta", "green", "blue", "yellow", "dim"],
    )


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
            common.output_message(f"Failed to fetch queue for {printer}: {e}", error=True)
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
            common.output_message(f"Failed to fetch printer list: {e}", error=True)

    if not all_jobs:
        common.output_message("No jobs in queue.")
        return

    rows = []
    for j in all_jobs:
        source = "Unknown"
        if j.source_info:
            source = j.source_info.public_name or j.source_info.first_name or "Unknown"

        rows.append([str(j.id), j.printer_uuid or "Unknown", j.state, j.file.name if j.file else "Unknown", source])

    common.output_table(
        "Job Queue",
        ["ID", "Printer", "State", "Name", "Source"],
        rows,
        column_styles=["cyan", "magenta", "green", "blue", "dim"],
    )


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
        common.output_message("Printer UUID is required. Provide --printer or set a default.", error=True)
        return
    try:
        job = client.get_job(resolved_printer_id, job_id)

        rows = [["ID", str(job.id)], ["State", str(job.state)]]
        if job.file:
            rows.append(["File", job.file.name])
        if job.progress is not None:
            rows.append(["Progress", f"{job.progress}%"])
        if job.time_printing:
            rows.append(["Time Printing", str(job.time_printing)])

        common.output_table(
            f"Job {job.id}",
            ["Field", "Value"],
            rows,
            column_styles=["cyan", None],
        )

        # Cancelable Objects
        if job.cancelable_objects:
            obj_rows = [[str(obj.id), obj.name] for obj in job.cancelable_objects]
            common.output_table(
                "Cancelable Objects",
                ["ID", "Name"],
                obj_rows,
                column_styles=["cyan", "white"],
            )
        else:
            common.output_message("No cancelable objects found for this job.")

        if detailed:
            import json

            detail_rows = []
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
                    detail_rows.append([k.title().replace("_", " "), val_str])

            if detail_rows:
                common.output_table(
                    "Detailed Information",
                    ["Field", "Value"],
                    detail_rows,
                    column_styles=["cyan", None],
                )

    except Exception as e:
        common.output_message(f"Failed to fetch job details: {e}", error=True)
