"""Raw API request commands."""

from __future__ import annotations

import json
import pathlib  # noqa: TC003
import sys
import typing

import cyclopts
import requests  # noqa: TC002
from rich import print as rprint

from prusa.connect.client.cli import common


def api_command(
    path: typing.Annotated[str, cyclopts.Parameter(help="API endpoint (e.g. /app/printers)")],
    method: typing.Annotated[str, cyclopts.Parameter(help="HTTP Method")] = "GET",
    data: typing.Annotated[str | None, cyclopts.Parameter(help="JSON data body")] = None,
    output: typing.Annotated[pathlib.Path | None, cyclopts.Parameter(help="Output file for response")] = None,
    stream: typing.Annotated[bool, cyclopts.Parameter(help="Stream response (useful for large files)")] = False,
    response_headers: typing.Annotated[bool, cyclopts.Parameter(help="Print response headers", alias=["-h"])] = False,
    response_body: typing.Annotated[bool, cyclopts.Parameter(help="Print response body", alias=["-b"])] = True,
):
    """Make a raw authenticated API request."""
    common.logger.debug(
        "Command started",
        command="api",
        method=method,
        path=path,
        data=data,
        output=output,
        stream=stream,
    )
    client = common.get_client()

    kwargs = {}
    if data:
        kwargs["json"] = json.loads(data)

    if stream:
        kwargs["stream"] = True

    # Use raw=True if output is specified OR stream is True
    # If streaming, we MUST use raw to get the response object

    try:
        res: requests.Response = client._request(method, path, raw=True, **kwargs)

        if response_headers:
            rprint(f"{getattr(res, 'status_code', None)} {getattr(res, 'reason', None)}")
            for k, v in res.headers.items():
                rprint(f"[bold]{k}:[/bold] {v}")
            rprint("")

        if stream:
            # Handle streaming
            if output and str(output) != "-":
                with open(output, "wb") as f:
                    for chunk in res.iter_content(chunk_size=8192):
                        f.write(chunk)
                rprint(f"[green]Streamed response to {output}[/green]")
            else:
                # Stream to stdout
                for chunk in res.iter_content(chunk_size=8192):
                    sys.stdout.buffer.write(chunk)
            return

        content_type = res.headers.get("Content-Type", "")
        # Normal (non-stream) handling
        if output:
            if str(output) == "-":
                if "application/json" in content_type.lower():
                    sys.stdout.write(json.dumps(res.json()))
                else:
                    if hasattr(res, "text"):
                        sys.stdout.write(res.text)
                    else:
                        sys.stdout.buffer.write(res.content)
            else:
                if "application/json" in content_type.lower():
                    with open(output, "w") as f:
                        json.dump(res.json(), f)
                else:
                    if hasattr(res, "text"):
                        with open(output, "w") as f:
                            f.write(res.text)
                    else:
                        output.write_bytes(res.content)
                rprint(f"[green]Response saved to {output}[/green]")
        else:
            if response_body:
                if "application/json" in content_type.lower():
                    print(json.dumps(res.json()))
                elif "text" in content_type.lower():
                    print(res.text)
                else:
                    sys.stdout.buffer.write(res.content)

    except Exception as e:
        if (output and str(output) == "-") or stream:
            # If piping or streaming, print error to stderr
            sys.stderr.write(f"API Request Failed: {e}\n")
        else:
            rprint(f"[red]API Request Failed: {e}[/red]")
