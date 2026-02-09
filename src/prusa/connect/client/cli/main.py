"""Main entry point for the CLI."""

import sys

import cyclopts

from prusa.connect.client import __version__
from prusa.connect.client.cli import common
from prusa.connect.client.cli.commands import api, auth, camera, file, job, printer, team

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

# Register Aliases and Commands
app.command(printer.printers_alias, name="printers")
app.command(camera.camera_alias, name="cameras")
app.command(job.jobs_alias, name="jobs")
app.command(file.files_alias, name="files")
app.command(team.teams_alias, name="teams")
app.command(api.api_command, name="api")
app.command(auth.auth_command, name="auth")


def main(args: list[str] | None = None):
    """Main entry point."""
    if args is None:
        args = sys.argv[1:]

    # Handle global logging flags early and robustly.
    # We use argparse.parse_known_args to extract just the flags we care about
    # without failing on unknown subcommand flags (like --detailed).
    import argparse

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--no-verbose", dest="verbose", action="store_false")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--no-debug", dest="debug", action="store_false")
    parser.set_defaults(verbose=False, debug=False)

    parsed_globals, remaining = parser.parse_known_args(args)

    # Configure logging
    common.configure_logging(parsed_globals.verbose, parsed_globals.debug)

    # Let cyclopts handle the full command parsing (subcommands, help, etc)
    try:
        app(remaining)
    except cyclopts.exceptions.CycloptsError as e:
        # Standard cyclopts error handling
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
