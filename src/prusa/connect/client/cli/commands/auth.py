"""Authentication commands."""

import contextlib
import datetime
import getpass
import json
import os
import sys
import typing

import cyclopts
from rich import print as rprint
from rich.table import Table

from prusa.connect.client import auth, exceptions
from prusa.connect.client.cli import common, config


def _auth_login():
    """Perform interactive login."""
    rprint("Logging in to Prusa Connect...")

    email = config.settings.prusa_email or os.environ.get("PRUSA_EMAIL")
    if not email:
        print("Email: ", end="", flush=True)
        email = input().strip()

    password = config.settings.prusa_password or os.environ.get("PRUSA_PASSWORD")
    if not password:
        password = getpass.getpass("Password: ")

    def otp_callback() -> str:
        print("Enter 2FA/TOTP Code: ", end="", flush=True)
        return input().strip()

    try:
        token_data = auth.interactive_login(email, str(password), otp_callback=otp_callback)

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


def _auth_show():
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


def _auth_clear():
    """Clear saved credentials."""
    path = config.settings.tokens_file
    if path.exists():
        path.unlink()
        rprint(f"[green]Removed tokens file: {path}[/green]")
    else:
        rprint(f"[yellow]No tokens file found at {path}[/yellow]")


def _auth_print_token(kind: typing.Literal["access", "identity"]):
    """Print raw token."""
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


def auth_command(
    action: typing.Annotated[
        typing.Literal["login", "show", "clear", "print-access-token", "print-identity-token"],
        cyclopts.Parameter(help="Auth action"),
    ],
):
    """Manage authentication settings."""
    common.logger.debug("Command started", command="auth", action=action)

    if action == "login":
        _auth_login()
    elif action == "show":
        _auth_show()
    elif action == "clear":
        _auth_clear()
    elif action == "print-access-token":
        _auth_print_token("access")
    elif action == "print-identity-token":
        _auth_print_token("identity")
