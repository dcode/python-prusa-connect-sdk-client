"""Data models for printer commands and arguments.

These models define how PRUSA connect commands and their required arguments are structured.

How to use the most important parts:
- `CommandDefinition`: Represents an executable command (like 'PAUSE_PRINT' or 'STOP_PRINT').
- `CommandArgument`: Describes a required or optional argument for a specific command.
Users typically encounter these when querying `PrusaConnectClient.get_printer_commands(uuid)`, receiving a
list of `CommandDefinition` objects explaining what can be done to the printer.
"""

import typing

import pydantic


class CommandArgument(pydantic.BaseModel):
    """Definition of a single argument for a printer command."""

    name: str
    type: typing.Literal["string", "integer", "boolean", "object", "number"]
    required: bool = False
    default: typing.Any | None = None
    description: str | None = None
    reference: str | None = None
    input: bool = True
    output: bool = False
    unit: str | None = None

    model_config = pydantic.ConfigDict(extra="ignore")


class CommandDefinition(pydantic.BaseModel):
    """Definition of a supported printer command."""

    command: str
    args: list[CommandArgument] = pydantic.Field(default_factory=list)
    description: str | None = None
    executable_from_state: list[str] = pydantic.Field(default_factory=list)
    template: str | None = None  # G-code template if applicable
    duplicates_allowed: bool = False

    model_config = pydantic.ConfigDict(extra="ignore")


class SupportedCommandsResponse(pydantic.BaseModel):
    """Response model for /supported-commands endpoint."""

    commands: list[CommandDefinition]
