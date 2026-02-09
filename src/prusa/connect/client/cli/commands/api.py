"""Raw API request commands."""

import json
import pathlib
import sys
import typing

import cyclopts
from rich import print as rprint

from prusa.connect.client.cli import common


def api_command(
    path: typing.Annotated[str, cyclopts.Parameter(help="API endpoint (e.g. /printers)")],
    method: typing.Annotated[str, cyclopts.Parameter(help="HTTP Method")] = "GET",
    data: typing.Annotated[str | None, cyclopts.Parameter(help="JSON data body")] = None,
    output: typing.Annotated[pathlib.Path | None, cyclopts.Parameter(help="Output file for response")] = None,
    stream: typing.Annotated[bool, cyclopts.Parameter(help="Stream response (useful for large files)")] = False,
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
    raw_mode = (output is not None) or stream

    try:
        res = client._request(method, path, raw=raw_mode, **kwargs)

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

        # Normal (non-stream) handling
        if output:
            if str(output) == "-":
                if hasattr(res, "content"):
                    sys.stdout.buffer.write(res.content)
                else:
                    print(json.dumps(res, indent=2))
            else:
                if hasattr(res, "content"):
                    output.write_bytes(res.content)
                else:
                    with open(output, "w") as f:
                        json.dump(res, f, indent=2)
                rprint(f"[green]Response saved to {output}[/green]")
        else:
            rprint(res)

    except Exception as e:
        if (output and str(output) == "-") or stream:
            # If piping or streaming, print error to stderr
            sys.stderr.write(f"API Request Failed: {e}\n")
        else:
            rprint(f"[red]API Request Failed: {e}[/red]")
