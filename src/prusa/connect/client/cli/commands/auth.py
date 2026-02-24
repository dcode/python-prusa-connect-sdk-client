"""Authentication commands."""

import contextlib
import datetime
import json
import os
import sys
import typing

import cyclopts
from rich.prompt import Confirm, Prompt

from prusa.connect.client import auth, exceptions
from prusa.connect.client.cli import common, config

auth_app = cyclopts.App(name="auth", help="Manage authentication settings")


@auth_app.command(name="login")
def login_command():
    """Perform interactive login."""
    # Always use rich console for interactive prompts regardless of format
    common.console.print("[bold blue]Logging in to Prusa Connect...[/bold blue]")

    default_email = config.settings.prusa_email or os.environ.get("PRUSA_EMAIL")
    email = Prompt.ask("Email", default=default_email)

    default_password = config.settings.prusa_password or os.environ.get("PRUSA_PASSWORD")
    if default_password:
        common.console.print("[dim]Using password from environment/config[/dim]")
        password = default_password
    else:
        password = Prompt.ask("Password", password=True)

    def otp_callback() -> str:
        return Prompt.ask("Enter 2FA/TOTP Code")

    try:
        token_data = auth.interactive_login(str(email), str(password), otp_callback=otp_callback)

        def save_tokens(data):
            path = config.settings.tokens_file
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            with contextlib.suppress(OSError):
                os.chmod(path, 0o600)

        save_tokens(token_data.dump_tokens())
        common.output_message(f"Authentication successful! Tokens saved to {config.settings.tokens_file}")

    except Exception as e:
        common.output_message(f"Authentication failed: {e}", error=True)
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
            common.output_message("Not authenticated or tokens expired.")
            return

    if not creds or not creds.tokens:
        common.output_message("No tokens found.")
        return

    t = creds.tokens

    def fmt_ts(ts):
        return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")

    fmt = common.get_output_format()

    if fmt == "json":
        # Serialize structured token data
        data: dict[str, dict[str, str | list[str] | dict[str, str]]] = {}
        if t.identity_token:
            identity: dict[str, str | list[str] | dict[str, str]] = {
                "user_id": str(t.identity_token.user_id),
                "issuer": t.identity_token.issuer,
                "token_id": t.identity_token.token_id,
            }
            if t.identity_token.user_info:
                identity["user_info"] = {k: str(v) for k, v in t.identity_token.user_info.items() if v}
            data["identity"] = identity
        if t.access_token:
            data["access_token"] = {
                "token_id": t.access_token.token_id,
                "expires": fmt_ts(t.access_token.expires_at.timestamp()),
                "scope": list(t.scope),
            }
        if t.refresh_token:
            data["refresh_token"] = {
                "token_id": t.refresh_token.token_id,
                "expires": fmt_ts(t.refresh_token.expires_at.timestamp()),
            }
        print(json.dumps(data))
    else:
        rows: list[list[str]] = []

        if t.identity_token:
            rows.append(["Identity", ""])
            rows.append(["  Subject (Sub)", str(t.identity_token.user_id)])
            rows.append(["  Issuer (Iss)", t.identity_token.issuer])
            rows.append(["  Token ID (JTI)", t.identity_token.token_id])
            if t.identity_token.user_info:
                for k, v in t.identity_token.user_info.items():
                    if v:
                        rows.append([f"  User.{k}", str(v)])

        if t.access_token:
            rows.append(["Access Token", ""])
            rows.append(["  Token ID (JTI)", t.access_token.token_id])
            rows.append(["  Expires", fmt_ts(t.access_token.expires_at.timestamp())])
            rows.append(["  Scope", ", ".join(t.scope)])

        if t.refresh_token:
            rows.append(["Refresh Token", ""])
            rows.append(["  Token ID (JTI)", t.refresh_token.token_id])
            rows.append(["  Expires", fmt_ts(t.refresh_token.expires_at.timestamp())])

        if fmt == "plain":
            print("# Authentication Status")
            for label, value in rows:
                print(f"{label}\t{value}")
        else:
            from rich.table import Table

            table = Table(title="Authentication Status", show_header=False)
            table.add_column("Key", style="bold")
            table.add_column("Value")
            for label, value in rows:
                table.add_row(label, value)
            common.console.print(table)


@auth_app.command(name="clear")
def clear_command():
    """Clear saved credentials."""
    path = config.settings.tokens_file
    if path.exists():
        if not Confirm.ask(f"Clear saved credentials at {path}?"):
            common.output_message("Aborted.")
            return
        path.unlink()
        common.output_message(f"Removed tokens file: {path}")
    else:
        common.output_message(f"No tokens file found at {path}")


def _print_token(kind: typing.Literal["access", "identity"]):
    """Helper to print raw token."""
    creds = auth.PrusaConnectCredentials.load_default()
    if creds and not creds.valid:
        with contextlib.suppress(exceptions.PrusaAuthError):
            creds.refresh()

    if not creds or not creds.tokens:
        common.output_message("No credentials found.", error=True)
        sys.exit(1)

    token = None
    if kind == "access" and creds.tokens.access_token:
        token = creds.tokens.access_token.raw_token
    elif kind == "identity" and creds.tokens.identity_token:
        token = creds.tokens.identity_token.raw_token

    if token:
        print(token)
    else:
        common.output_message(f"No {kind} token found.", error=True)
        sys.exit(1)


@auth_app.command(name="print-access-token")
def print_access_token_command():
    """Print the raw access token."""
    _print_token("access")


@auth_app.command(name="print-identity-token")
def print_identity_token_command():
    """Print the raw identity token."""
    _print_token("identity")
