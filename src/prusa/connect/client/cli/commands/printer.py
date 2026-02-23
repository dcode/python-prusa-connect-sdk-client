"""Printer management commands."""

import datetime
import fnmatch
import json
import typing

import cyclopts
from rich import print as rprint
from rich.table import Table

from prusa.connect.client import exceptions, models
from prusa.connect.client.cli import common, config

printer_app = cyclopts.App(name="printer", help="Printer management")
files_printer_app = cyclopts.App(name="files", help="Printer file management")
printer_app.command(files_printer_app)


def _send_printer_command(printer_ids: list[str], command: str):
    """Helper to send a command to multiple printers."""
    client = common.get_client()

    for pid in printer_ids:
        try:
            if client.printers.send_command(pid, command):
                rprint(f"[green]Sent {command} to {pid}[/green]")
        except Exception as e:
            rprint(f"[red]Failed to send {command} to {pid}: {e}[/red]")


@printer_app.command(name="list")
def printer_list(
    pattern: typing.Annotated[str, cyclopts.Parameter(name="pattern", help="Glob pattern to filter names")] = "*",
):
    """List all printers associated with the account."""
    common.logger.debug("Command started", command="printer list", pattern=pattern)
    client = common.get_client()
    printers = client.printers.list_printers()
    common.logger.info("Found printers", count=len(printers))

    table = Table(title="Printers")
    table.add_column("Name", style="cyan")
    table.add_column("UUID", style="magenta")
    table.add_column("State", style="green")
    table.add_column("Model", style="blue")

    # Filter
    filtered = [p for p in printers if fnmatch.fnmatch(p.name or "", pattern)]

    for p in filtered:
        common.logger.debug("Printer", json=p.model_dump_json())
        state_str = str(p.printer_state) if p.printer_state else "UNKNOWN"
        table.add_row(
            p.name or "Unknown",
            p.uuid or "Unknown",
            state_str,
            p.printer_model or "N/A",
        )
    common.console.print(table)


def printers_alias(
    pattern: typing.Annotated[str, cyclopts.Parameter(name="pattern", help="Glob pattern to filter names")] = "*",
):
    """List all printers (alias for 'printer list')."""
    printer_list(pattern=pattern)


@printer_app.command(name="show")
def printer_show(
    printer_id: typing.Annotated[str | None, cyclopts.Parameter(help="Printer UUID")] = None,
    detailed: typing.Annotated[
        bool, cyclopts.Parameter(name=["--detailed", "-d"], help="Show detailed information (MMU, Fans, Axis)")
    ] = False,
):
    """Show detailed status for a specific printer."""
    resolved_id = printer_id or config.settings.default_printer_id
    if not resolved_id:
        rprint(
            "[red]No printer ID provided and no default configured.[/red]\n"
            "[dim]Hint: Run 'prusactl printer list' to find a UUID, then\n"
            "'prusactl printer set-current <uuid>' to set the default.[/dim]"
        )
        return

    common.logger.debug("Command started", command="printer show", printer_id=resolved_id)
    client = common.get_client()

    try:
        p = client.printers.get(resolved_id)

        # Basic Info Table
        table = Table(title=f"Printer: {p.name}")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="magenta")

        table.add_row("UUID", p.uuid or "N/A")
        table.add_row("State", p.printer_state or "N/A")
        table.add_row("Model", p.printer_model or "N/A")

        # Firmware
        fw_str = p.firmware_version or "Unknown"
        if p.support and p.support.latest and p.support.latest != p.firmware_version:
            # Check if current != latest
            # The 'current' field in support might be more accurate or redundant with p.firmware_version
            fw_str += f" [yellow](Latest: {p.support.latest})[/yellow]"
        table.add_row("Firmware", fw_str)

        # Location / Team
        if p.location:
            table.add_row("Location", p.location)
        if p.team_name:
            table.add_row("Team", p.team_name)

        # Network Info
        if p.network_info:
            table.add_section()
            if p.network_info.hostname:
                table.add_row("Hostname", p.network_info.hostname)
            if p.network_info.lan_ipv4:
                table.add_row("IP Address", p.network_info.lan_ipv4)

        # Last Online
        if p.last_online:
            last_seen = datetime.datetime.fromtimestamp(p.last_online).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
            table.add_row("Last Online", last_seen)

        # Tool 1 Material (Default View)
        material = "N/A"
        # Try to find material from tools or slots
        if p.tools and "1" in p.tools:
            material = p.tools["1"].material or "N/A"

        # If no tool material, maybe checking active slot?
        if (material == "N/A" or material == "---") and p.slot and p.slot.active is not None:
            active_slot_key = str(p.slot.active)
            if p.slot.slots and active_slot_key in p.slot.slots:
                m = p.slot.slots[active_slot_key].material
                if m and m != "---":
                    material = f"{m} (Slot {active_slot_key})"

        table.add_section()
        table.add_row("Material", material)
        if p.telemetry:
            table.add_row("Nozzle", f"{p.telemetry.temp_nozzle}°C")
            table.add_row("Bed", f"{p.telemetry.temp_bed}°C")

        # Job
        if p.job:
            table.add_section()
            table.add_row("Job", p.job.display_name or "Unknown")
            table.add_row("Progress", f"{p.job.progress}%")
            if p.job.time_printing:
                table.add_row("Time Printing", str(p.job.time_printing))
            if p.job.time_remaining and p.job.time_remaining.total_seconds() > 0:
                table.add_row("Time Remaining", str(p.job.time_remaining))

        common.console.print(table)

        if detailed:
            # Detailed View - MMU Slots
            if p.slot and p.slot.slots:
                slot_table = Table(title="MMU Slots")
                slot_table.add_column("Slot", style="cyan")
                slot_table.add_column("Material", style="magenta")
                slot_table.add_column("Temp", style="yellow")

                # Sort by slot ID
                sorted_slots = sorted(p.slot.slots.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999)
                for slot_id, slot_data in sorted_slots:
                    slot_table.add_row(
                        slot_id, slot_data.material or "---", str(slot_data.temp) if slot_data.temp else "N/A"
                    )
                common.console.print(slot_table)

            # Tools Detail (Fans etc)
            if p.tools:
                tool_table = Table(title="Tools / Heads")
                tool_table.add_column("Tool", style="cyan")
                tool_table.add_column("Nozzle", style="green")
                tool_table.add_column("Material", style="magenta")
                tool_table.add_column("Fan Print", style="blue")
                tool_table.add_column("Fan Hotend", style="blue")

                for tool_id, tool_data in p.tools.items():
                    tool_table.add_row(
                        tool_id,
                        str(tool_data.nozzle_diameter) if tool_data.nozzle_diameter else "N/A",
                        tool_data.material or "---",
                        f"{tool_data.fan_print}%" if tool_data.fan_print is not None else "N/A",
                        f"{tool_data.fan_hotend}%" if tool_data.fan_hotend is not None else "N/A",
                    )
                common.console.print(tool_table)

            # Axis Info
            axis_table = Table(title="Axis Positions")
            axis_table.add_column("Axis", style="cyan")
            axis_table.add_column("Position", style="yellow")
            if p.axis_x is not None:
                axis_table.add_row("X", str(p.axis_x))
            if p.axis_y is not None:
                axis_table.add_row("Y", str(p.axis_y))
            if p.axis_z is not None:
                axis_table.add_row("Z", str(p.axis_z))

            if axis_table.row_count > 0:
                common.console.print(axis_table)

            rprint("\n[bold]Raw Detailed Information:[/bold]")
            detail_table = Table(show_header=False, box=None)
            for k, v in p.model_dump(mode="json").items():
                if v is not None and k not in [
                    "uuid",
                    "name",
                    "printer_state",
                    "printer_model",
                    "firmware_version",
                    "network_info",
                    "support",
                    "tools",
                    "slot",
                    "location",
                    "team_name",
                    "last_online",
                    "telemetry",
                    "job",
                ]:
                    val_str = json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                    detail_table.add_row(f"[cyan]{k}[/cyan]:", val_str)
            common.console.print(detail_table)

    except exceptions.PrusaConnectError as e:
        rprint(f"[red]Error:[/red] {e}")


@printer_app.command(name="pause")
def printer_pause(
    printer_ids: typing.Annotated[list[str] | None, cyclopts.Parameter(help="Printer UUIDs")] = None,
):
    """Pause print on one or more printers."""
    ids = printer_ids or ([config.settings.default_printer_id] if config.settings.default_printer_id else [])
    if not ids:
        rprint("[red]No printer IDs provided and no default configured.[/red]")
        return

    common.logger.debug("Command started", command="printer pause", printer_ids=ids)
    _send_printer_command(ids, "PAUSE_PRINT")


@printer_app.command(name="resume")
def printer_resume(
    printer_ids: typing.Annotated[list[str] | None, cyclopts.Parameter(help="Printer UUIDs")] = None,
):
    """Resume print on one or more printers."""
    ids = printer_ids or ([config.settings.default_printer_id] if config.settings.default_printer_id else [])
    if not ids:
        rprint("[red]No printer IDs provided and no default configured.[/red]")
        return

    common.logger.debug("Command started", command="printer resume", printer_ids=ids)
    _send_printer_command(ids, "RESUME_PRINT")


@printer_app.command(name="stop")
def printer_stop(
    printer_ids: typing.Annotated[list[str] | None, cyclopts.Parameter(help="Printer UUIDs")] = None,
    reason: typing.Annotated[str | None, cyclopts.Parameter(help="Job failure reason (e.g. SPAGHETTI_MONSTER)")] = None,
    note: typing.Annotated[str, cyclopts.Parameter(help="Optional note for the failure")] = "",
):
    """Stop print on one or more printers, optionally setting a failure reason."""
    ids = printer_ids or ([config.settings.default_printer_id] if config.settings.default_printer_id else [])
    if not ids:
        rprint("[red]No printer IDs provided and no default configured.[/red]")
        return

    common.logger.debug("Command started", command="printer stop", printer_ids=ids, reason=reason)
    client = common.get_client()

    for pid in ids:
        try:
            # 1. Stop the print
            if client.stop_print(pid):
                rprint(f"[green]Sent STOP_PRINT to {pid}[/green]")

                # 2. Set reason if provided
                if reason:
                    # We need the current job ID to set the reason
                    # Fetch printer status to get job ID
                    try:
                        p = client.printers.get(pid)
                        if p.job and p.job.id:
                            # Validate reason string against Enum

                            # Accept a case insensitive reason string
                            try:
                                enum_reason = models.JobFailureTag(reason.upper())
                                client.set_job_failure_reason(pid, p.job.id, enum_reason, note)
                                rprint(f"[green]Set failure reason '{enum_reason}' for Job {p.job.id}[/green]")
                            except ValueError:
                                rprint(
                                    f"[yellow]Invalid reason code '{reason}'. Supported: "
                                    f"{', '.join([r.value for r in models.JobFailureTag])}[/yellow]"
                                )
                        else:
                            rprint(
                                "[yellow]Could not determine Job ID to set failure reason "
                                "(printer has no active job info).[/yellow]"
                            )
                    except Exception as e:
                        rprint(f"[red]Failed to set failure reason: {e}[/red]")

            else:
                rprint(f"[red]Failed to send STOP_PRINT to {pid}[/red]")
        except Exception as e:
            rprint(f"[red]Failed to send STOP_PRINT to {pid}: {e}[/red]")


@printer_app.command(name="cancel-object")
def printer_cancel_object(
    object_id: typing.Annotated[int, cyclopts.Parameter(help="Object ID to cancel")],
    printer_id: typing.Annotated[str | None, cyclopts.Parameter(help="Printer UUID")] = None,
):
    """Cancel a specific object during print."""
    resolved_id = printer_id or config.settings.default_printer_id
    if not resolved_id:
        rprint(
            "[red]No printer ID provided and no default configured.[/red]\n"
            "[dim]Hint: Run 'prusactl printer list' to find a UUID, then "
            "'prusactl printer set-current <uuid>' to set the default.[/dim]"
        )
        return

    common.logger.debug("Command started", command="printer cancel-object", printer_id=resolved_id, object_id=object_id)
    client = common.get_client()
    try:
        if client.cancel_object(resolved_id, object_id):
            rprint(f"[green]Successfully sent CANCEL_OBJECT for object {object_id} to {resolved_id}[/green]")
        else:
            rprint("[red]Failed to send CANCEL_OBJECT command[/red]")
    except Exception as e:
        rprint(f"[red]Error:[/red] {e}")


@printer_app.command(name="move")
def printer_move(
    printer_id: typing.Annotated[str | None, cyclopts.Parameter(help="Printer UUID")] = None,
    x: typing.Annotated[float | None, cyclopts.Parameter(name="--x", help="Target X position")] = None,
    y: typing.Annotated[float | None, cyclopts.Parameter(name="--y", help="Target Y position")] = None,
    z: typing.Annotated[float | None, cyclopts.Parameter(name="--z", help="Target Z position")] = None,
    e: typing.Annotated[float | None, cyclopts.Parameter(name="--e", help="Extruder movement")] = None,
    speed: typing.Annotated[float | None, cyclopts.Parameter(name="--speed", help="Feedrate")] = None,
):
    """Move printer axis."""
    resolved_id = printer_id or config.settings.default_printer_id
    if not resolved_id:
        rprint(
            "[red]No printer ID provided and no default configured.[/red]\n"
            "[dim]Hint: Run 'prusactl printer list' to find a UUID, then "
            "'prusactl printer set-current <uuid>' to set the default.[/dim]"
        )
        return

    common.logger.debug("Command started", command="printer move", printer_id=resolved_id)
    client = common.get_client()
    try:
        if client.move_axis(resolved_id, x=x, y=y, z=z, e=e, speed=speed):
            rprint(f"[green]Successfully sent MOVE command to {resolved_id}[/green]")
        else:
            rprint("[red]Failed to send MOVE command[/red]")
    except Exception as e:
        rprint(f"[red]Error:[/red] {e}")


@printer_app.command(name="flash")
def printer_flash(
    file_path: typing.Annotated[
        str, cyclopts.Parameter(help="Path to .bbf file on printer storage (e.g. /usb/fw.bbf)")
    ],
    printer_id: typing.Annotated[str | None, cyclopts.Parameter(help="Printer UUID")] = None,
):
    """Flash firmware from a file on the printer's storage."""
    resolved_id = printer_id or config.settings.default_printer_id
    if not resolved_id:
        rprint(
            "[red]No printer ID provided and no default configured.[/red]\n"
            "[dim]Hint: Run 'prusactl printer list' to find a UUID, then "
            "'prusactl printer set-current <uuid>' to set the default.[/dim]"
        )
        return

    common.logger.debug("Command started", command="printer flash", printer_id=resolved_id, file_path=file_path)
    client = common.get_client()
    try:
        if client.flash_firmware(resolved_id, file_path):
            rprint(f"[green]Successfully sent FLASH command to {resolved_id}[/green]")
        else:
            rprint("[red]Failed to send FLASH command[/red]")
    except Exception as e:
        rprint(f"[red]Error:[/red] {e}")


@printer_app.command(name="commands")
def printer_commands(
    printer_id: typing.Annotated[str | None, cyclopts.Parameter(help="Printer UUID")] = None,
):
    """List supported commands for a specific printer."""
    resolved_id = printer_id or config.settings.default_printer_id
    if not resolved_id:
        rprint(
            "[red]No printer ID provided and no default configured.[/red]\n"
            "[dim]Hint: Run 'prusactl printer list' to find a UUID, then "
            "'prusactl printer set-current <uuid>' to set the default.[/dim]"
        )
        return

    common.logger.debug("Command started", command="printer commands", printer_id=resolved_id)
    client = common.get_client()

    try:
        commands = client.get_supported_commands(resolved_id)

        # Deduplicate commands
        # The API can return "duplicates" that differ only by internal fields like 'template'.
        # We group by name and signature (arguments) to avoid showing redundant entries.
        unique_map: dict[str, list] = {}
        for cmd in commands:
            if cmd.command not in unique_map:
                unique_map[cmd.command] = []

            # Check for signature match
            is_duplicate = False
            current_args_json = json.dumps(
                [a.model_dump(include={"name", "type", "required"}) for a in cmd.args], sort_keys=True
            )

            for existing in unique_map[cmd.command]:
                existing_args_json = json.dumps(
                    [a.model_dump(include={"name", "type", "required"}) for a in existing.args], sort_keys=True
                )
                if current_args_json == existing_args_json:
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique_map[cmd.command].append(cmd)

        unique_commands = [cmd for sublist in unique_map.values() for cmd in sublist]

        table = Table(title=f"Supported Commands for {printer_id}")
        table.add_column("Command", style="cyan")
        table.add_column("Description", style="white")
        table.add_column("Arguments", style="yellow")
        table.add_column("Valid States", style="green")

        for cmd in sorted(unique_commands, key=lambda x: x.command):
            # Format arguments
            args_str = ""
            if cmd.args:
                arg_list = []
                for arg in cmd.args:
                    req_mark = "*" if arg.required else ""
                    arg_list.append(f"{arg.name}{req_mark}")
                args_str = ", ".join(arg_list)

            # Format states
            states_str = ", ".join(cmd.executable_from_state) if cmd.executable_from_state else "ALL"
            if len(states_str) > 30:
                states_str = states_str[:27] + "..."

            table.add_row(cmd.command, cmd.description or "", args_str, states_str)

        common.console.print(table)
        if not commands:
            rprint("[yellow]No supported commands found (or printer does not support command discovery).[/yellow]")

    except Exception as e:
        rprint(f"[red]Error fetching commands:[/red] {e}")


@printer_app.command(name="command")
def printer_execute_command(
    command_name: typing.Annotated[str, cyclopts.Parameter(help="Command Name (e.g. CANCEL_OBJECT)")],
    printer_id: typing.Annotated[str | None, cyclopts.Parameter(help="Printer UUID")] = None,
    args: typing.Annotated[str, cyclopts.Parameter(name="--args", help="JSON arguments string")] = "",
    **kwargs,
):
    """Execute a specific command on a printer.

    Arguments can be passed as flags (e.g. --object-id 1) or as a JSON string via --args.

    !!! Warning "Use with extreme caution."

        This command allows arbitrary commands and arguments to be sent to the printer via the Prusa Connect API.
        Minimal validation is performed on the arguments by `prusactl` and there is no guarantee the Prusa Connect API
        or your printer will accept or process them successfully.



    Args:
        command_name: The name of the command to execute.
        printer_id: The ID of the printer to execute the command on. If not provided, the default printer
            ID will be used.
        args: A JSON string of arguments to pass to the command.
        **kwargs: Additional keyword arguments to pass to the command.
    """
    resolved_id = printer_id or config.settings.default_printer_id
    if not resolved_id:
        rprint(
            "[red]No printer ID provided and no default configured.[/red]\n"
            "[dim]Hint: Run 'prusactl printer list' to find a UUID, then "
            "'prusactl printer set-current <uuid>' to set the default.[/dim]"
        )
        return

    common.logger.debug(
        "Command started",
        command="printer command",
        printer_id=resolved_id,
        command_name=command_name,
        json_args=args,
        kwargs=kwargs,
    )
    client = common.get_client()

    try:
        # 1. Parse Arguments
        final_args = {}

        # Load from JSON if provided
        if args:
            try:
                json_parsed = json.loads(args)
                if not isinstance(json_parsed, dict):
                    raise ValueError("--args must be a JSON object")
                final_args.update(json_parsed)
            except json.JSONDecodeError as e:
                rprint(f"[red]Invalid JSON in --args:[/red] {e}")
                return

        # Load from kwargs (flags)
        # cyclopts passes these as strings
        # client.execute_printer_command does simple type checking:
        # if arg_def.type == "integer" and not isinstance(val, int): raise...
        # So we MUST cast here.

        # To cast correctly, we need the command definition!

        # Fetch definition first to know types
        supported = client.get_supported_commands(resolved_id)
        cmd_def = next((c for c in supported if c.command == command_name), None)

        if not cmd_def:
            rprint(f"[red]Command '{command_name}' not supported by printer {resolved_id}.[/red]")
            # Suggest close matches?
            matches = fnmatch.filter([c.command for c in supported], f"*{command_name}*")
            if matches:
                rprint(f"Did you mean: {', '.join(matches)}?")
            return

        # Merge kwargs into final_args, converting types
        for k, v in kwargs.items():
            # Match k to arg name (command args are snake_case usually)
            # CLI flags are kebab-case but cyclopts normalizes them to snake_case

            # Find the argument definition
            arg_def = next((a for a in cmd_def.args if a.name == k), None)
            if arg_def:
                # Cast based on type
                if arg_def.type == "integer":
                    try:
                        final_args[k] = int(v)
                    except ValueError:
                        rprint(f"[red]Argument '{k}' must be an integer (got '{v}')[/red]")
                        return
                elif arg_def.type == "number":
                    try:
                        final_args[k] = float(v)
                    except ValueError:
                        rprint(f"[red]Argument '{k}' must be a number (got '{v}')[/red]")
                        return
                elif arg_def.type == "boolean":
                    # CLI flags for bools: usually presence means True
                    # cyclopts **kwargs treats flags with values
                    if str(v).lower() in ("true", "1", "yes", "on"):
                        final_args[k] = True
                    elif str(v).lower() in ("false", "0", "no", "off"):
                        final_args[k] = False
                    else:
                        rprint(f"[red]Argument '{k}' must be a boolean (got '{v}')[/red]")
                        return
                else:
                    final_args[k] = v
            else:
                # Unknown argument
                # Client doesn't strict check unknown extra args in 'execute_printer_command',
                # it blindly passes everything to send_command after verifying *required*.
                # But it DOES check known args for types.
                final_args[k] = v

        # 2. Execute
        success = client.execute_printer_command(resolved_id, command_name, final_args)
        if success:
            rprint(f"[green]Successfully sent command '{command_name}' to {resolved_id}[/green]")
        else:
            rprint(f"[red]Failed to send command '{command_name}'[/red]")

    except ValueError as e:
        rprint(f"[red]Validation Error:[/red] {e}")
    except Exception as e:
        rprint(f"[red]Error executing command:[/red] {e}")


@printer_app.command(name="storages")
def printer_storages(
    printer_id: typing.Annotated[str | None, cyclopts.Parameter(help="Printer UUID")] = None,
):
    """List storage devices attached to a printer."""
    resolved_id = printer_id or config.settings.default_printer_id
    if not resolved_id:
        rprint(
            "[red]No printer ID provided and no default configured.[/red]\n"
            "[dim]Hint: Run 'prusactl printer list' to find a UUID, then "
            "'prusactl printer set-current <uuid>' to set the default.[/dim]"
        )
        return

    client = common.get_client()
    try:
        storages = client.get_printer_storages(resolved_id)
        table = Table(title=f"Storages for {resolved_id}")
        table.add_column("Name", style="cyan")
        table.add_column("Type", style="green")
        table.add_column("Mountpoint", style="magenta")
        table.add_column("Free", style="yellow")
        table.add_column("ReadOnly", style="red")

        for s in storages:
            free_str = f"{s.free_space / 1024 / 1024 / 1024:.2f} GB" if s.free_space else "N/A"
            table.add_row(
                s.name,
                s.type,
                s.mountpoint or s.path,
                free_str,
                "Yes" if s.read_only else "No",
            )
        common.console.print(table)
    except Exception as e:
        rprint(f"[red]Error:[/red] {e}")


@files_printer_app.command(name="list")
def printer_files_list(
    printer_id: typing.Annotated[str | None, cyclopts.Parameter(help="Printer UUID")] = None,
):
    """List files on the printer's storage."""
    resolved_id = printer_id or config.settings.default_printer_id
    if not resolved_id:
        rprint(
            "[red]No printer ID provided and no default configured.[/red]\n"
            "[dim]Hint: Run 'prusactl printer list' to find a UUID, then "
            "'prusactl printer set-current <uuid>' to set the default.[/dim]"
        )
        return

    client = common.get_client()
    try:
        files = client.get_printer_files(resolved_id)
        table = Table(title=f"Files on {resolved_id}")
        table.add_column("Name", style="cyan")
        table.add_column("Path", style="magenta")
        table.add_column("Size", style="green")
        table.add_column("Modified", style="yellow")

        for f in files:
            size_str = f"{f.size / 1024 / 1024:.2f} MB" if f.size else "N/A"
            mtime_str = "N/A"
            if f.m_timestamp:
                mtime_str = datetime.datetime.fromtimestamp(f.m_timestamp).strftime("%Y-%m-%d %H:%M:%S")

            table.add_row(f.name, f.path, size_str, mtime_str)
        common.console.print(table)
    except Exception as e:
        rprint(f"[red]Error:[/red] {e}")


@files_printer_app.command(name="upload")
def printer_files_upload(
    path: typing.Annotated[str, cyclopts.Parameter(help="Local path to file")],
    printer_id: typing.Annotated[str | None, cyclopts.Parameter(help="Printer UUID")] = None,
    destination: typing.Annotated[str, cyclopts.Parameter(help="Destination path on printer (e.g. /usb/)")] = "/usb/",
):
    """Upload a file to a printer's storage."""
    resolved_id = printer_id or config.settings.default_printer_id
    if not resolved_id:
        rprint(
            "[red]No printer ID provided and no default configured.[/red]\n"
            "[dim]Hint: Run 'prusactl printer list' to find a UUID, then "
            "'prusactl printer set-current <uuid>' to set the default.[/dim]"
        )
        return

    client = common.get_client()
    try:
        p = client.printers.get(resolved_id)
        teams = client.teams.list_teams()
        # Find team by team_name
        target_team = next((t for t in teams if t.name == p.team_name), None)
        if not target_team and teams:
            target_team = teams[0]
            rprint(f"[yellow]Could not resolve team ID for printer. Using first team: {target_team.name}[/yellow]")

        if not target_team:
            rprint("[red]Could not determine team for upload.[/red]")
            return

        from prusa.connect.client.cli.commands import file

        file.file_upload(path=path, team_id=target_team.id, destination=destination)

    except Exception as e:
        rprint(f"[red]Error:[/red] {e}")


@files_printer_app.command(name="download")
def printer_files_download(
    file_hash: typing.Annotated[str, cyclopts.Parameter(help="File hash to download")],
    printer_id: typing.Annotated[str | None, cyclopts.Parameter(help="Printer UUID")] = None,
    output: typing.Annotated[str | None, cyclopts.Parameter(help="Optional output path")] = None,
):
    """Download a file that belongs to a printer's team."""
    resolved_id = printer_id or config.settings.default_printer_id
    if not resolved_id:
        rprint(
            "[red]No printer ID provided and no default configured.[/red]\n"
            "[dim]Hint: Run 'prusactl printer list' to find a UUID, then "
            "'prusactl printer set-current <uuid>' to set the default.[/dim]"
        )
        return

    client = common.get_client()
    try:
        p = client.printers.get(resolved_id)
        teams = client.teams.list_teams()
        target_team = next((t for t in teams if t.name == p.team_name), None)
        if not target_team and teams:
            target_team = teams[0]

        if not target_team:
            rprint("[red]Could not determine team for download.[/red]")
            return

        from prusa.connect.client.cli.commands import file

        file.file_download(file_hash=file_hash, team_id=target_team.id, output=output)

    except Exception as e:
        rprint(f"[red]Error:[/red] {e}")


@printer_app.command(name="set-current")
def set_current_printer(printer_id: typing.Annotated[str, cyclopts.Parameter(help="Printer UUID")]):
    """Set the default printer UUID for future commands."""
    config.settings.default_printer_id = printer_id
    config.save_json_config(config.settings)
    rprint(f"[green]Successfully set default printer to {printer_id}[/green]")
