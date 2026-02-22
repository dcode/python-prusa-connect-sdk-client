"""Main entry point for the CLI."""

import sys
import typing

import cyclopts

from prusa.connect.client import __version__
from prusa.connect.client.cli import common
from prusa.connect.client.cli.commands import api, auth, camera, file, job, printer, stats, team

# Define the App
app = cyclopts.App(
    name="prusactl",
    help="Prusa Connect CLI and API Client",
    version=__version__,
    version_flags=["--version"],
    help_flags=["--help"],
)
app.register_install_completion_command(add_to_startup=False)

# Mount Sub-Apps
app.command(printer.printer_app)
app.command(camera.camera_app)
app.command(job.job_app)
app.command(file.file_app)
app.command(team.team_app)
app.command(stats.stats_app)

# Register Aliases and Commands
app.command(printer.printers_alias, name="printers")
app.command(camera.camera_alias, name="cameras")
app.command(job.jobs_alias, name="jobs")
app.command(file.files_alias, name="files")
app.command(team.teams_alias, name="teams")
app.command(api.api_command, name="api")
app.command(auth.auth_app)


@app.meta.default
def entry_point(
    tokens: typing.Annotated[list[str] | None, cyclopts.Parameter(show=False, allow_leading_hyphen=True)] = None,
    verbose: typing.Annotated[
        bool, cyclopts.Parameter(name=["--verbose", "-v"], help="Enable verbose logging")
    ] = False,
    debug: typing.Annotated[bool, cyclopts.Parameter(name=["--debug"], help="Enable debug logging")] = False,
):
    """Main entry point handling global flags."""
    # Configure logging
    common.configure_logging(verbose, debug)

    if tokens is None:
        tokens = []
    # Let cyclopts handle the full command parsing (subcommands, help, etc)
    try:
        app(tokens)
    except cyclopts.exceptions.CycloptsError as e:
        # Standard cyclopts error handling
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main(args: list[str] | None = None):
    """Main entry point."""
    if args is None:
        args = sys.argv[1:]

    try:
        app.meta(args)
    except cyclopts.exceptions.CycloptsError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        from prusa.connect.client import exceptions

        if isinstance(e, exceptions.PrusaApiError):
            print(f"API Error: {e}", file=sys.stderr)
            if e.response_body:
                print(f"Details: {e.response_body}", file=sys.stderr)
        elif isinstance(e, exceptions.PrusaNetworkError):
            print(f"Network Error: {e}", file=sys.stderr)
        else:
            print(f"Unexpected Error: {e}", file=sys.stderr)
            common.logger.exception("An unexpected error occurred")
        sys.exit(1)


if __name__ == "__main__":
    main()
