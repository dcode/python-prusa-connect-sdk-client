"""Team commands."""

import sys
import typing

import cyclopts
from rich import print as rprint
from rich.table import Table

from prusa.connect.client.cli import common, config
from prusa.connect.client.cli.commands.job import job_list

team_app = cyclopts.App(name="team", help="Team management")


@team_app.command(name="list")
def list_teams():
    """List all teams the user belongs to."""
    client = common.get_client()
    teams = client.get_teams()

    table = Table(title="Teams")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Role", style="magenta")
    table.add_column("Organization ID", style="blue")

    for team in teams:
        table.add_row(
            str(team.id),
            team.name,
            str(team.role or "N/A"),
            str(team.organization_id or "N/A"),
        )
    rprint(table)


@team_app.command(name="show")
def show_team(
    team_id: typing.Annotated[int | None, cyclopts.Parameter(help="Team ID")] = None,
    detailed: typing.Annotated[
        bool, cyclopts.Parameter(name=["--detailed", "-d"], help="Show detailed information about the team")
    ] = False,
):
    """Show details for a specific team."""
    team_id_to_use = team_id or config.settings.default_team_id
    if team_id_to_use is None:
        rprint("[red]Error: Team ID not provided and no default is set.[/red]")
        sys.exit(1)

    client = common.get_client()
    try:
        team = client.get_team(team_id_to_use)
    except Exception as e:
        rprint(f"[red]Error fetching team {team_id_to_use}: {e}[/red]")
        sys.exit(1)

    table = Table(title=f"Team Details: {team.name}")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("ID", str(team.id))
    table.add_row("Name", team.name)
    table.add_row("Role", str(team.role or "N/A"))
    if team.description:
        table.add_row("Description", team.description)
    if team.capacity is not None:
        table.add_row("Capacity", str(team.capacity))
    if team.organization_id:
        table.add_row("Organization ID", str(team.organization_id))
    if team.user_count is not None:
        table.add_row("User Count", str(team.user_count))

    rprint(table)

    if getattr(team, "users", None):
        users_table = Table(title="Team Users")
        users_table.add_column("ID", style="cyan")
        users_table.add_column("Name", style="green")
        users_table.add_column("Username", style="magenta")
        users_table.add_column("Rights", style="yellow")

        for u in team.users:
            name_parts = [p for p in [u.first_name, u.last_name] if p]
            name = " ".join(name_parts) if name_parts else "N/A"
            rights = []
            if u.rights_ro:
                rights.append("RO")
            if u.rights_rw:
                rights.append("RW")
            if u.rights_use:
                rights.append("USE")

            users_table.add_row(str(u.id), name, u.public_name or "N/A", ", ".join(rights) if rights else "NONE")
        rprint(users_table)

    if detailed:
        import json

        rprint("\n[bold]Detailed Information:[/bold]")
        detail_table = Table(show_header=False, box=None)
        for k, v in team.model_dump(mode="json").items():
            if v is not None and k not in [
                "id",
                "name",
                "role",
                "description",
                "capacity",
                "organization_id",
                "user_count",
                "users",
            ]:
                val_str = json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                detail_table.add_row(f"[cyan]{k}[/cyan]:", val_str)
        common.console.print(detail_table)


@team_app.command(name="add-user")
def add_team_user(
    email: typing.Annotated[str, cyclopts.Parameter(help="Email address of user to invite")],
    team_id: typing.Annotated[int | None, cyclopts.Parameter(help="Team ID")] = None,
    rights_ro: typing.Annotated[bool, cyclopts.Parameter(help="Grant read-only rights")] = True,
    rights_use: typing.Annotated[bool, cyclopts.Parameter(help="Grant use rights")] = False,
    rights_rw: typing.Annotated[bool, cyclopts.Parameter(help="Grant read-write rights")] = False,
):
    """Invite a user to a team."""
    team_id_to_use = team_id or config.settings.default_team_id
    if team_id_to_use is None:
        rprint("[red]Error: Team ID not provided and no default is set.[/red]")
        sys.exit(1)

    client = common.get_client()
    try:
        if client.add_team_user(team_id_to_use, email, rights_ro, rights_use, rights_rw):
            rprint(f"[green]Successfully sent invitation to {email}[/green]")
    except Exception as e:
        from prusa.connect.client import exceptions

        if isinstance(e, exceptions.PrusaApiError):
            import json

            try:
                err_data = json.loads(e.response_body)
                msg = err_data.get("message", e.response_body)
                rprint(f"[red]Failed to add user:[/red] {msg}")
            except json.JSONDecodeError:
                rprint(f"[red]Failed to add user:[/red] {e.response_body}")
        else:
            rprint(f"[red]Failed to add user: {e}[/red]")


@team_app.command(name="set-current")
def set_current_team(
    team_id: typing.Annotated[int, cyclopts.Parameter(help="Team ID")],
):
    """Set the default team ID for future commands."""
    config.settings.default_team_id = team_id
    config.save_json_config(config.settings)
    rprint(f"[green]Successfully set default team to {team_id}[/green]")


def teams_alias():
    """List all teams (alias for 'team list')."""
    list_teams()


@team_app.command(name="jobs")
def team_jobs_alias(
    team: typing.Annotated[int | None, cyclopts.Parameter(help="Team ID")] = None,
    printer: typing.Annotated[str | None, cyclopts.Parameter(help="Printer UUID")] = None,
    state: typing.Annotated[list[str] | None, cyclopts.Parameter(help="Job state")] = None,
    limit: typing.Annotated[int | None, cyclopts.Parameter(help="Limit number of jobs")] = None,
):
    """List jobs (alias for 'job list')."""
    team_id_to_use = team or config.settings.default_team_id
    if team_id_to_use is None:
        rprint("[red]Error: Team ID not provided and no default is set.[/red]")
        sys.exit(1)

    job_list(team=team_id_to_use, printer=printer, state=state, limit=limit)
