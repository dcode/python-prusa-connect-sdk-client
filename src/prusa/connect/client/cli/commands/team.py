"""Team commands."""

import json
import sys
import typing

import cyclopts

from prusa.connect.client.cli import common, config
from prusa.connect.client.cli.commands.job import job_list

team_app = cyclopts.App(name="team", help="Team management")


@team_app.command(name="list")
def list_teams():
    """List all teams the user belongs to."""
    client = common.get_client()
    teams = client.teams.list_teams()

    rows = [[str(team.id), team.name, str(team.role or "N/A"), str(team.organization_id or "N/A")] for team in teams]
    common.output_table(
        "Teams",
        ["ID", "Name", "Role", "Organization ID"],
        rows,
        column_styles=["cyan", "green", "magenta", "blue"],
    )


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
        common.output_message("Error: Team ID not provided and no default is set.", error=True)
        sys.exit(1)

    client = common.get_client()
    try:
        team = client.teams.get(team_id_to_use)
    except Exception as e:
        common.output_message(f"Error fetching team {team_id_to_use}: {e}", error=True)
        sys.exit(1)

    rows = [
        ["ID", str(team.id)],
        ["Name", team.name],
        ["Role", str(team.role or "N/A")],
    ]
    if team.description:
        rows.append(["Description", team.description])
    if team.capacity is not None:
        rows.append(["Capacity", str(team.capacity)])
    if team.organization_id:
        rows.append(["Organization ID", str(team.organization_id)])
    if team.user_count is not None:
        rows.append(["User Count", str(team.user_count)])

    common.output_table(
        f"Team Details: {team.name}",
        ["Property", "Value"],
        rows,
        column_styles=["cyan", "green"],
    )

    if getattr(team, "users", None):
        user_rows = []
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
            user_rows.append([str(u.id), name, u.public_name or "N/A", ", ".join(rights) if rights else "NONE"])

        common.output_table(
            "Team Users",
            ["ID", "Name", "Username", "Rights"],
            user_rows,
            column_styles=["cyan", "green", "magenta", "yellow"],
        )

    if detailed:
        detail_rows = []
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
                detail_rows.append([k, val_str])

        if detail_rows:
            common.output_table(
                "Detailed Information",
                ["Field", "Value"],
                detail_rows,
                column_styles=["cyan", None],
            )


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
        common.output_message("Error: Team ID not provided and no default is set.", error=True)
        sys.exit(1)

    client = common.get_client()
    try:
        if client.add_team_user(team_id_to_use, email, rights_ro, rights_use, rights_rw):
            common.output_message(f"Successfully sent invitation to {email}")
    except Exception as e:
        from prusa.connect.client import exceptions

        if isinstance(e, exceptions.PrusaApiError):
            try:
                err_data = json.loads(e.response_body)
                msg = err_data.get("message", e.response_body)
                common.output_message(f"Failed to add user: {msg}", error=True)
            except json.JSONDecodeError:
                common.output_message(f"Failed to add user: {e.response_body}", error=True)
        else:
            common.output_message(f"Failed to add user: {e}", error=True)


@team_app.command(name="set-current")
def set_current_team(
    team_id: typing.Annotated[int, cyclopts.Parameter(help="Team ID")],
):
    """Set the default team ID for future commands."""
    config.settings.default_team_id = team_id
    config.save_json_config(config.settings)
    common.output_message(f"Successfully set default team to {team_id}")


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
        common.output_message("Error: Team ID not provided and no default is set.", error=True)
        sys.exit(1)

    job_list(team=team_id_to_use, printer=printer, state=state, limit=limit)
