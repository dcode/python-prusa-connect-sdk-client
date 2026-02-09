# Design Doc: Robust Printer Command Execution

## Objective

Implement robust support for executing printer-specific commands using the
definition retrieved from the `/app/printers/{printer_uuid}/supported-commands`
endpoint. This ensures that only valid commands and arguments are sent to the
printer, preventing errors and potential damage.

## Problem Statement

Currently, the client supports a static set of commands defined in
`PrinterCommand` enum. However, printers may support different commands or
require arguments for specific commands (e.g., `G-code` sending, fan speed,
etc.). The supported commands and their arguments are dynamic and available via
the API. We need to fetch, cache, and use these definitions to validate commands
before sending them.

## Proposed Solution

### 1. Data Models

We will define Pydantic models to represent the command structure defined in
`supported-commands_response.json`.

```python
from typing import Any, Literal
from pydantic import BaseModel, Field


class CommandArgument(BaseModel):
    name: str
    type: Literal["string", "integer", "boolean", "object", "number"]
    required: bool = False
    default: Any | None = None
    description: str | None = None
    # "input", "output", "unit", "reference" fields are also present but maybe less critical for validation?
    # We should include them for completeness if useful.


class CommandDefinition(BaseModel):
    command: str
    args: list[CommandArgument] = Field(default_factory=list)
    description: str | None = None
    executable_from_state: list[str] = Field(default_factory=list)
    template: str | None = None  # Some commands have a G-code template
```

### 2. Caching Strategy

To avoid fetching supported commands before every execution, we will cache the
definitions.

- **Scope**: Per `PrusaConnectClient` instance (or global if commands are
  universal? No, they are per-printer).
- **Key**: `printer_uuid`.
- **Mechanism**: In-memory dictionary
  `_supported_commands_cache: dict[str, list[CommandDefinition]]`.
- **TTL**: We can implement a simple "fetch if missing" or "explicit refresh"
  mechanism. Since supported commands theoretically shouldn't change often
  command-to-command, fetching once per session (or lazy loading) is
  efficient.
- **Fail-safe**: If cache is missing, fetch it.

### 3. API Client Extensions (`PrusaConnectClient`)

#### New Methods

- `get_supported_commands(printer_uuid: str) -> list[CommandDefinition]`:

    - Checks cache.
    - If miss, calls `GET /app/printers/{printer_uuid}/supported-commands`.
    - Parses response into `list[CommandDefinition]`.
    - Updates cache.
    - Returns list.

- `execute_printer_command(printer_uuid: str, command: str, args: dict[str, Any] | None = None) -> None`:

    - call `get_supported_commands(printer_uuid)`.
    - Find `CommandDefinition` for `command`.
    - **Validation**:
        - Check if `command` exists.
        - Check `executable_from_state` (requires knowing current state? - OPTIONAL
          for MVP, might need extra call or rely on recent state).
          *Self-correction: The server likely validates state too, but client-side
          check is nice if we have state.*
        - **Argument Validation**:
            - Iterate over `def.args`.
            - Check required args are present.
            - Check types (int, bool, str).
    - If valid, send `POST /app/printers/{printer_uuid}/command` (or whatever the
      endpoint is).
        - Payload: `{"command": command, "args": args}` (Need to verify exact
          payload structure).

### 4. Payload Structure Verification

We need to confirm the `POST` payload format for commands with arguments.
*Assumption*: It matches the `PrinterCommand` use but with an `args` key?\
*Observation*: `supported-commands_response.json` shows how commands are
*defined*. We need to know how to *send* them. The standard command endpoint is
usually `POST /app/printers/{printer_uuid}/commands` (or similar). Existing code
likely uses `POST /app/printers/{printer_uuid}/command` with
`{ "command": "CMD" }`. We should verify if it accepts
`{ "command": "CMD", "args": { ... } }` or similar.

### 5. Implementation Steps

1. **Define Models**: Create `src/prusa_connect/command_models.py` (or add to
   `models.py`).
2. **Update Client**: Add `get_supported_commands` and
   `execute_specific_command`.
3. **Validation Logic**: Implement the validation loop.

## Alternative Considerations

- **Dynamic Method Generation**: We could generate methods on the fly, but
  that's complex and messy for type checkers.
- **Strict Typing**: We can return a generic "valid" object or raise specific
  exceptions (`CommandValidationError`).

## Validation Plan

1. **Unit Tests**:
    - Mock `supported-commands` response.
    - Test `validate_command` with valid/invalid args.
    - Test caching mechanism.
2. **Manual Verification**:
    - Use `execute_printer_command` against a real printer (if available) or mock
      server.
    - Attempt to send a command with missing args and verify it fails *before*
      sending.
