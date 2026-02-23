"""Authentication commands."""

import contextlib
import datetime
import json
import os
import sys
import typing

import cyclopts
from rich import print as rprint
from rich.prompt import Confirm, Prompt
from rich.table import Table

from prusa.connect.client import auth, exceptions
from prusa.connect.client.cli import common, config

auth_app = cyclopts.App(name="auth", help="Manage authentication settings")


@auth_app.command(name="login")
def login_command():
    """Perform interactive login."""
    rprint("[bold blue]Logging in to Prusa Connect...[/bold blue]")

    default_email = config.settings.prusa_email or os.environ.get("PRUSA_EMAIL")
    email = Prompt.ask("Email", default=default_email)

    default_password = config.settings.prusa_password or os.environ.get("PRUSA_PASSWORD")
    if default_password:
        rprint("[dim]Using password from environment/config[/dim]")
        password = default_password
    else:
        password = Prompt.ask("Password", password=True)

    def otp_callback() -> str:
        return Prompt.ask("Enter 2FA/TOTP Code")

    try:
        token_data = auth.interactive_login(str(email), str(password), otp_callback=otp_callback)

        def save_tokens(data):
            path = config.settings.tokens_file
            # Ensure parent dir exists
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            # Best-effort secure permissions
            with contextlib.suppress(OSError):
                os.chmod(path, 0o600)

        save_tokens(token_data.dump_tokens())
        rprint(f"[green]Authentication successful! Tokens saved to {config.settings.tokens_file}[/green]")

    except Exception as e:
        rprint(f"[bold red]Authentication failed: {e}[/bold red]")
        sys.exit(1)


@auth_app.command(name="show")
def show_command():
    """Show current authentication status."""
    creds = auth.PrusaConnectCredentials.load_default()
    if not creds or not creds.valid:
        try:
            if creds:
                creds.refresh()
        except exceptions.PrusaAuthError:
            rprint("[yellow]Not authenticated or tokens expired.[/yellow]")
            return

    if not creds or not creds.tokens:
        rprint("[yellow]No tokens found.[/yellow]")
        return

    t = creds.tokens
    table = Table(title="Authentication Status", show_header=False)

    # helper
    def fmt_ts(ts):
        return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")

    if t.identity_token:
        table.add_row("[bold]Identity[/bold]", "")
        table.add_row("  Subject (Sub)", str(t.identity_token.user_id))
        table.add_row("  Issuer (Iss)", t.identity_token.issuer)
        table.add_row("  Token ID (JTI)", t.identity_token.token_id)
        if t.identity_token.user_info:
            for k, v in t.identity_token.user_info.items():
                if v:
                    table.add_row(f"  User.{k}", str(v))

    if t.access_token:
        table.add_row("[bold]Access Token[/bold]", "")
        table.add_row("  Token ID (JTI)", t.access_token.token_id)
        table.add_row("  Expires", fmt_ts(t.access_token.expires_at.timestamp()))
        table.add_row("  Scope", ", ".join(t.scope))

    if t.refresh_token:
        table.add_row("[bold]Refresh Token[/bold]", "")
        table.add_row("  Token ID (JTI)", t.refresh_token.token_id)
        table.add_row("  Expires", fmt_ts(t.refresh_token.expires_at.timestamp()))

    common.console.print(table)


@auth_app.command(name="clear")
def clear_command():
    """Clear saved credentials."""
    path = config.settings.tokens_file
    if path.exists():
        if not Confirm.ask(f"Clear saved credentials at {path}?"):
            rprint("[dim]Aborted.[/dim]")
            return
        path.unlink()
        rprint(f"[green]Removed tokens file: {path}[/green]")
    else:
        rprint(f"[yellow]No tokens file found at {path}[/yellow]")


def _print_token(kind: typing.Literal["access", "identity"]):
    """Helper to print raw token."""
    creds = auth.PrusaConnectCredentials.load_default()
    # Try refresh if needed
    if creds and not creds.valid:
        with contextlib.suppress(exceptions.PrusaAuthError):
            creds.refresh()

    if not creds or not creds.tokens:
        rprint("[red]No credentials found.[/red]", file=sys.stderr)
        sys.exit(1)

    token = None
    if kind == "access" and creds.tokens.access_token:
        token = creds.tokens.access_token.raw_token
    elif kind == "identity" and creds.tokens.identity_token:
        token = creds.tokens.identity_token.raw_token

    if token:
        print(token)
    else:
        rprint(f"[red]No {kind} token found.[/red]", file=sys.stderr)
        sys.exit(1)


@auth_app.command(name="print-access-token")
def print_access_token_command():
    """Print the raw access token."""
    _print_token("access")


@auth_app.command(name="print-identity-token")
def print_identity_token_command():
    """Print the raw identity token."""
    _print_token("identity")


# Legacy alias for backward compatibility if needed, but we're replacing the command structure.
# We can export auth_app as the main interface.
